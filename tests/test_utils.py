"""Unit tests for the notebook validation helpers in ``tests/notebook_tests/utils.py``.

These exercise each pure function with hand-built ``CellInfo`` fixtures so that
regressions in the shared validator logic show up quickly without needing real
notebooks.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.notebook_tests.utils import (
    CellInfo,
    extract_pip_dependencies,
    find_dated_model_ids,
    get_notebook_kernel_info,
    load_notebook,
    parse_notebook_cells,
    validate_all_cells_executed,
    validate_cell_execution_order,
    validate_no_empty_cells,
    validate_no_error_outputs,
    validate_no_hardcoded_secrets,
    validate_uses_env_for_api_key,
)


def code(index: int, source: str, execution_count: int | None = 1, outputs=None) -> CellInfo:
    """Build a code ``CellInfo`` for tests."""
    outs = outputs or []
    return CellInfo(
        index=index,
        cell_type="code",
        execution_count=execution_count,
        source=source,
        outputs=outs,
        has_error_output=any(o.get("output_type") == "error" for o in outs),
        is_empty=not source.strip(),
    )


def md(index: int, source: str) -> CellInfo:
    """Build a markdown ``CellInfo`` for tests."""
    return CellInfo(
        index=index,
        cell_type="markdown",
        execution_count=None,
        source=source,
        outputs=[],
        is_empty=not source.strip(),
    )


class TestValidateCellExecutionOrder:
    def test_empty_notebook_passes(self):
        assert validate_cell_execution_order([]) == []

    def test_no_executed_cells_passes(self):
        cells = [code(0, "print(1)", execution_count=None)]
        assert validate_cell_execution_order(cells) == []

    def test_sequential_passes(self):
        cells = [code(i, f"x = {i}", execution_count=i + 1) for i in range(3)]
        assert validate_cell_execution_order(cells) == []

    def test_skips_markdown_cells(self):
        cells = [
            code(0, "a = 1", execution_count=1),
            md(1, "# heading"),
            code(2, "a = 2", execution_count=2),
        ]
        assert validate_cell_execution_order(cells) == []

    def test_backwards_jump_reports_once(self):
        cells = [
            code(0, "a", execution_count=3),
            code(1, "b", execution_count=2),
        ]
        issues = validate_cell_execution_order(cells)
        assert len(issues) == 1
        assert "out of order" in issues[0]

    def test_gap_reports_once(self):
        cells = [
            code(0, "a", execution_count=1),
            code(1, "b", execution_count=5),
        ]
        issues = validate_cell_execution_order(cells)
        assert len(issues) == 1
        assert "expected 2, got 5" in issues[0]

    def test_unexecuted_cells_ignored(self):
        cells = [
            code(0, "a", execution_count=1),
            code(1, "b", execution_count=None),
            code(2, "c", execution_count=2),
        ]
        assert validate_cell_execution_order(cells) == []


class TestValidateAllCellsExecuted:
    def test_all_executed(self):
        cells = [code(0, "a", execution_count=1)]
        assert validate_all_cells_executed(cells) == []

    def test_unexecuted_code_cell_flagged(self):
        cells = [code(0, "a", execution_count=None)]
        issues = validate_all_cells_executed(cells)
        assert len(issues) == 1
        assert "not been executed" in issues[0]

    def test_empty_code_cell_skipped(self):
        cells = [code(0, "", execution_count=None)]
        assert validate_all_cells_executed(cells) == []

    def test_markdown_cells_skipped(self):
        cells = [md(0, "# heading")]
        assert validate_all_cells_executed(cells) == []


class TestValidateNoErrorOutputs:
    def test_no_outputs(self):
        assert validate_no_error_outputs([code(0, "a")]) == []

    def test_error_output_flagged(self):
        cell = code(
            0,
            "1/0",
            outputs=[
                {"output_type": "error", "ename": "ZeroDivisionError", "evalue": "division by zero"}
            ],
        )
        issues = validate_no_error_outputs([cell])
        assert len(issues) == 1
        assert "ZeroDivisionError" in issues[0]


class TestValidateNoEmptyCells:
    def test_empty_returns_warnings(self):
        warnings = validate_no_empty_cells([code(0, "")])
        assert len(warnings) == 1

    def test_non_empty_returns_none(self):
        assert validate_no_empty_cells([code(0, "x = 1")]) == []


class TestValidateNoHardcodedSecrets:
    def test_clean_cell_passes(self):
        cells = [code(0, "client = Anthropic()")]
        assert validate_no_hardcoded_secrets(cells) == []

    def test_literal_anthropic_key_flagged(self):
        cells = [code(0, 'key = "sk-ant-api03-abcDEF123456789_-test"')]
        issues = validate_no_hardcoded_secrets(cells)
        assert len(issues) == 1

    def test_hardcoded_assignment_flagged(self):
        cells = [code(0, '"ANTHROPIC_API_KEY"="my-secret-value-12345"')]
        issues = validate_no_hardcoded_secrets(cells)
        assert len(issues) == 1

    def test_markdown_cells_ignored(self):
        cells = [md(0, "Set ANTHROPIC_API_KEY=sk-ant-leak in your .env")]
        # Markdown is documentation; only code cells are scanned.
        assert validate_no_hardcoded_secrets(cells) == []

    def test_only_flagged_once_per_cell(self):
        cells = [code(0, 'a = "sk-ant-abc-123"\nb = "sk-ant-def-456"')]
        # The function breaks after first match per cell (current behaviour).
        assert len(validate_no_hardcoded_secrets(cells)) == 1


class TestValidateUsesEnvForApiKey:
    def test_default_client_ok(self):
        cells = [code(0, "client = Anthropic()")]
        assert validate_uses_env_for_api_key(cells) == []

    def test_env_var_ok(self):
        cells = [code(0, 'client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])')]
        assert validate_uses_env_for_api_key(cells) == []

    def test_literal_string_warns(self):
        cells = [code(0, 'client = Anthropic(api_key="my-key-placeholder")')]
        warnings = validate_uses_env_for_api_key(cells)
        assert len(warnings) == 1
        assert "string literal" in warnings[0]

    def test_sk_literal_not_double_reported(self):
        # Already covered by validate_no_hardcoded_secrets; should not duplicate.
        cells = [code(0, 'client = Anthropic(api_key="sk-ant-leak")')]
        assert validate_uses_env_for_api_key(cells) == []


class TestFindDatedModelIds:
    def test_dated_api_model_flagged(self):
        cells = [code(0, 'model="claude-sonnet-4-5-20250929"')]
        assert find_dated_model_ids(cells) == [(0, "claude-sonnet-4-5-20250929")]

    def test_bedrock_model_ignored(self):
        cells = [
            code(0, 'model="anthropic.claude-haiku-4-5-20251001-v1:0"'),
            code(1, 'model="global.anthropic.claude-opus-4-6-v1"'),
        ]
        assert find_dated_model_ids(cells) == []

    def test_non_dated_alias_ignored(self):
        cells = [code(0, 'model="claude-sonnet-4-6"')]
        assert find_dated_model_ids(cells) == []

    def test_legacy_dated_id_flagged(self):
        cells = [code(0, 'model="claude-3-5-sonnet-20241022"')]
        hits = find_dated_model_ids(cells)
        assert hits == [(0, "claude-3-5-sonnet-20241022")]

    def test_markdown_cells_skipped(self):
        cells = [md(0, "Use claude-sonnet-4-5-20250929 for...")]
        assert find_dated_model_ids(cells) == []


class TestExtractPipDependencies:
    def test_percent_pip(self):
        cells = [code(0, "%pip install anthropic pandas")]
        assert set(extract_pip_dependencies(cells)) == {"anthropic", "pandas"}

    def test_bang_pip(self):
        cells = [code(0, "!pip install -q voyageai")]
        assert extract_pip_dependencies(cells) == ["voyageai"]

    def test_pinned_version_stripped(self):
        cells = [code(0, "%pip install anthropic>=0.71.0 numpy==2.3.4")]
        assert set(extract_pip_dependencies(cells)) == {"anthropic", "numpy"}

    def test_extras_stripped(self):
        cells = [code(0, "%pip install anthropic[bedrock]")]
        assert extract_pip_dependencies(cells) == ["anthropic"]

    def test_no_pip_command(self):
        assert extract_pip_dependencies([code(0, "import anthropic")]) == []


class TestNotebookLoading:
    def test_parse_cells_marks_errors(self, tmp_path: Path):
        nb = {
            "cells": [
                {
                    "cell_type": "code",
                    "execution_count": 1,
                    "source": ["print(1)\n"],
                    "outputs": [{"output_type": "error", "ename": "X", "evalue": "y"}],
                },
                {"cell_type": "markdown", "source": ["# title"], "metadata": {}},
            ],
            "metadata": {"kernelspec": {"name": "python3", "language": "python"}},
            "nbformat": 4,
            "nbformat_minor": 5,
        }
        nb_path = tmp_path / "nb.ipynb"
        nb_path.write_text(json.dumps(nb))

        loaded = load_notebook(nb_path)
        cells = parse_notebook_cells(loaded)

        assert len(cells) == 2
        assert cells[0].has_error_output
        assert cells[1].cell_type == "markdown"
        assert not cells[1].has_error_output

    def test_get_kernel_info(self):
        nb = {
            "metadata": {
                "kernelspec": {"name": "python3", "display_name": "Python 3", "language": "python"},
                "language_info": {"name": "python", "version": "3.11.0"},
            }
        }
        info = get_notebook_kernel_info(nb)
        assert info["language"] == "python"
        assert info["language_version"] == "3.11.0"

    def test_get_kernel_info_falls_back_to_language_info(self):
        nb = {"metadata": {"language_info": {"name": "python"}}}
        info = get_notebook_kernel_info(nb)
        assert info["language"] == "python"
        assert info["kernel_name"] == "unknown"


def test_parse_notebook_cells_preserves_order():
    nb = {
        "cells": [
            {"cell_type": "markdown", "source": ["# A"]},
            {"cell_type": "code", "execution_count": 1, "source": ["x=1\n"], "outputs": []},
            {"cell_type": "code", "execution_count": 2, "source": ["x=2\n"], "outputs": []},
        ]
    }
    cells = parse_notebook_cells(nb)
    assert [c.index for c in cells] == [0, 1, 2]
    assert [c.cell_type for c in cells] == ["markdown", "code", "code"]


# Sanity guard: ensure ``parse_notebook_cells`` doesn't crash on a totally empty
# notebook, since pytest_generate_tests can parameterize odd inputs.
def test_parse_empty_notebook():
    assert parse_notebook_cells({"cells": []}) == []


@pytest.mark.parametrize(
    "src,expected",
    [
        ('Anthropic(api_key="")', 0),  # empty literal -> no match (requires non-empty)
        ("# api_key=os.environ['X']", 0),
        ('Anthropic(api_key = "literal" )', 1),
    ],
)
def test_validate_uses_env_for_api_key_parametrized(src: str, expected: int):
    assert len(validate_uses_env_for_api_key([code(0, src)])) == expected
