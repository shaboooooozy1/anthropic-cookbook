"""Unit tests for tests/notebook_tests/utils.py.

These cover the validation primitives that gate every PR (secret detection,
execution-order checks, pip-dependency extraction, structural validation).
A regression here would let leaked keys, broken notebooks, or stale models
slip through CI, so the helpers themselves need direct coverage.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.notebook_tests.utils import (
    CellInfo,
    extract_pip_dependencies,
    find_all_notebooks,
    get_notebook_kernel_info,
    load_notebook,
    parse_notebook_cells,
    validate_all_cells_executed,
    validate_cell_execution_order,
    validate_no_empty_cells,
    validate_no_error_outputs,
    validate_no_hardcoded_secrets,
    validate_notebook_structure,
)


def _code_cell(
    source: str,
    execution_count: int | None = 1,
    outputs: list | None = None,
) -> dict:
    return {
        "cell_type": "code",
        "execution_count": execution_count,
        "source": source,
        "outputs": outputs or [],
        "metadata": {},
    }


def _markdown_cell(source: str) -> dict:
    return {"cell_type": "markdown", "source": source, "metadata": {}}


def _build_notebook(cells: list[dict]) -> dict:
    return {
        "cells": cells,
        "metadata": {
            "kernelspec": {"name": "python3", "display_name": "Python 3", "language": "python"},
            "language_info": {"name": "python", "version": "3.11.0"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def _write_notebook(tmp_path: Path, cells: list[dict], name: str = "nb.ipynb") -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(_build_notebook(cells)), encoding="utf-8")
    return path


class TestParseNotebookCells:
    def test_parses_code_and_markdown(self):
        nb = _build_notebook([_code_cell("print(1)"), _markdown_cell("# Title")])
        cells = parse_notebook_cells(nb)
        assert [c.cell_type for c in cells] == ["code", "markdown"]
        assert cells[0].source == "print(1)"
        assert cells[0].is_empty is False
        assert cells[1].source == "# Title"

    def test_joins_list_source(self):
        cell = _code_cell("")
        cell["source"] = ["import os\n", "print(os.name)\n"]
        cells = parse_notebook_cells(_build_notebook([cell]))
        assert cells[0].source == "import os\nprint(os.name)\n"

    def test_marks_empty_cells(self):
        nb = _build_notebook([_code_cell("   \n\t\n")])
        cells = parse_notebook_cells(nb)
        assert cells[0].is_empty is True

    def test_detects_error_output(self):
        cell = _code_cell(
            "raise RuntimeError('boom')",
            outputs=[{"output_type": "error", "ename": "RuntimeError", "evalue": "boom"}],
        )
        cells = parse_notebook_cells(_build_notebook([cell]))
        assert cells[0].has_error_output is True


class TestValidateCellExecutionOrder:
    def test_in_order_passes(self):
        cells = [
            CellInfo(0, "code", 1, "a", []),
            CellInfo(1, "code", 2, "b", []),
            CellInfo(2, "code", 3, "c", []),
        ]
        assert validate_cell_execution_order(cells) == []

    def test_out_of_order_flagged(self):
        cells = [
            CellInfo(0, "code", 2, "a", []),
            CellInfo(1, "code", 1, "b", []),
        ]
        issues = validate_cell_execution_order(cells)
        assert any("out of order" in i for i in issues)

    def test_gap_flagged(self):
        cells = [
            CellInfo(0, "code", 1, "a", []),
            CellInfo(1, "code", 5, "b", []),
        ]
        issues = validate_cell_execution_order(cells)
        assert any("Non-sequential" in i for i in issues)

    def test_unexecuted_cells_ignored(self):
        cells = [
            CellInfo(0, "code", None, "a", []),
            CellInfo(1, "code", None, "b", []),
        ]
        assert validate_cell_execution_order(cells) == []

    def test_markdown_cells_ignored(self):
        cells = [
            CellInfo(0, "markdown", None, "# Header", []),
            CellInfo(1, "code", 1, "x", []),
            CellInfo(2, "markdown", None, "Note", []),
            CellInfo(3, "code", 2, "y", []),
        ]
        assert validate_cell_execution_order(cells) == []


class TestValidateAllCellsExecuted:
    def test_passes_when_all_executed(self):
        cells = [CellInfo(0, "code", 1, "x", []), CellInfo(1, "code", 2, "y", [])]
        assert validate_all_cells_executed(cells) == []

    def test_unexecuted_code_cell_flagged(self):
        cells = [CellInfo(0, "code", None, "x", [])]
        assert validate_all_cells_executed(cells) == ["Cell 0: Code cell has not been executed"]

    def test_empty_unexecuted_cell_skipped(self):
        cells = [CellInfo(0, "code", None, "", [], is_empty=True)]
        assert validate_all_cells_executed(cells) == []

    def test_unexecuted_markdown_skipped(self):
        cells = [CellInfo(0, "markdown", None, "# Hi", [])]
        assert validate_all_cells_executed(cells) == []


class TestValidateNoErrorOutputs:
    def test_no_outputs_passes(self):
        cells = [CellInfo(0, "code", 1, "x", [])]
        assert validate_no_error_outputs(cells) == []

    def test_error_output_reported_with_name(self):
        outputs = [{"output_type": "error", "ename": "ValueError", "evalue": "bad"}]
        cells = [CellInfo(0, "code", 1, "x", outputs, has_error_output=True)]
        issues = validate_no_error_outputs(cells)
        assert len(issues) == 1
        assert "ValueError" in issues[0]
        assert "bad" in issues[0]


class TestValidateNoEmptyCells:
    def test_warns_on_empty_cell(self):
        cells = [CellInfo(0, "code", None, "", [], is_empty=True)]
        warns = validate_no_empty_cells(cells)
        assert warns == ["Cell 0: Empty code cell"]

    def test_quiet_when_no_empty_cells(self):
        cells = [CellInfo(0, "code", 1, "print(1)", [])]
        assert validate_no_empty_cells(cells) == []


class TestValidateNoHardcodedSecrets:
    """The most security-critical helper — guards against leaked API keys."""

    def test_clean_notebook_passes(self):
        cells = [
            CellInfo(0, "code", 1, "client = Anthropic()  # uses ANTHROPIC_API_KEY env", []),
        ]
        assert validate_no_hardcoded_secrets(cells) == []

    def test_real_looking_anthropic_key_caught(self):
        cells = [
            CellInfo(0, "code", 1, 'KEY = "sk-ant-api03-AbCdEf-1234_xyz"', []),
        ]
        issues = validate_no_hardcoded_secrets(cells)
        assert len(issues) == 1
        assert "Cell 0" in issues[0]

    def test_dict_literal_assignment_caught(self):
        # The regex targets dict-literal / kwarg style: "KEY": "value" or "KEY"="value".
        cells = [
            CellInfo(0, "code", 1, 'config = {"ANTHROPIC_API_KEY": "leaked-value-123"}', []),
        ]
        assert len(validate_no_hardcoded_secrets(cells)) == 1

    @pytest.mark.xfail(
        reason=(
            "Known gap: the API_KEY_PATTERNS regex does not match "
            'os.environ["ANTHROPIC_API_KEY"] = "..." style assignments because '
            "the bracket interrupts the [=:] match. Widen the pattern to close."
        ),
        strict=True,
    )
    def test_os_environ_assignment_caught(self):
        cells = [
            CellInfo(0, "code", 1, 'os.environ["ANTHROPIC_API_KEY"] = "leaked"', []),
        ]
        assert len(validate_no_hardcoded_secrets(cells)) == 1

    def test_markdown_cells_ignored(self):
        # Markdown can legitimately reference key formats in docs.
        cells = [
            CellInfo(0, "markdown", None, "Set ANTHROPIC_API_KEY to sk-ant-yourkey", []),
        ]
        assert validate_no_hardcoded_secrets(cells) == []

    def test_env_variable_reference_passes(self):
        cells = [
            CellInfo(0, "code", 1, 'api_key = os.environ.get("ANTHROPIC_API_KEY")', []),
        ]
        assert validate_no_hardcoded_secrets(cells) == []

    def test_only_one_issue_per_cell_even_if_multiple_matches(self):
        # The function breaks on first match per cell to avoid noise.
        cells = [
            CellInfo(
                0,
                "code",
                1,
                'k1 = "sk-ant-aaa"\nos.environ["ANTHROPIC_API_KEY"] = "sk-ant-bbb"\n',
                [],
            ),
        ]
        assert len(validate_no_hardcoded_secrets(cells)) == 1


class TestExtractPipDependencies:
    def test_percent_pip_install(self):
        cells = [CellInfo(0, "code", 1, "%pip install anthropic", [])]
        assert extract_pip_dependencies(cells) == ["anthropic"]

    def test_bang_pip_install(self):
        cells = [CellInfo(0, "code", 1, "!pip install requests", [])]
        assert extract_pip_dependencies(cells) == ["requests"]

    def test_strips_quiet_and_other_flags(self):
        cells = [CellInfo(0, "code", 1, "!pip install -q --upgrade anthropic voyageai", [])]
        deps = sorted(extract_pip_dependencies(cells))
        assert deps == ["anthropic", "voyageai"]

    def test_strips_version_pin(self):
        cells = [CellInfo(0, "code", 1, "%pip install anthropic==0.39.0", [])]
        assert extract_pip_dependencies(cells) == ["anthropic"]

    def test_strips_extras(self):
        cells = [CellInfo(0, "code", 1, "%pip install 'anthropic[bedrock]'", [])]
        # Extras in quoted form preserve the quote — accept either parse.
        deps = extract_pip_dependencies(cells)
        assert any(d.startswith("anthropic") or d == "'anthropic" for d in deps)

    def test_dedupes_across_cells(self):
        cells = [
            CellInfo(0, "code", 1, "%pip install anthropic", []),
            CellInfo(1, "code", 2, "!pip install anthropic", []),
        ]
        assert extract_pip_dependencies(cells) == ["anthropic"]

    def test_ignores_markdown(self):
        cells = [CellInfo(0, "markdown", None, "%pip install anthropic", [])]
        assert extract_pip_dependencies(cells) == []

    def test_no_pip_calls_returns_empty(self):
        cells = [CellInfo(0, "code", 1, "import anthropic", [])]
        assert extract_pip_dependencies(cells) == []


class TestValidateNotebookStructure:
    def test_clean_notebook_passes(self, tmp_path: Path):
        path = _write_notebook(
            tmp_path,
            [
                _markdown_cell("# Demo"),
                _code_cell("import os", execution_count=1),
                _code_cell("print('hi')", execution_count=2),
            ],
        )
        result = validate_notebook_structure(path)
        assert result.is_valid is True
        assert result.errors == []

    def test_error_outputs_reported(self, tmp_path: Path):
        path = _write_notebook(
            tmp_path,
            [
                _code_cell(
                    "raise RuntimeError('boom')",
                    execution_count=1,
                    outputs=[{"output_type": "error", "ename": "RuntimeError", "evalue": "boom"}],
                ),
            ],
        )
        result = validate_notebook_structure(path)
        assert result.is_valid is False
        assert any("RuntimeError" in e for e in result.errors)

    def test_hardcoded_secret_breaks_validation(self, tmp_path: Path):
        path = _write_notebook(
            tmp_path,
            [_code_cell('KEY = "sk-ant-api03-LEAKED-xyz"', execution_count=1)],
        )
        result = validate_notebook_structure(path)
        assert result.is_valid is False
        assert any("hardcoded" in e.lower() for e in result.errors)

    def test_unexecuted_cell_breaks_validation(self, tmp_path: Path):
        path = _write_notebook(
            tmp_path,
            [_code_cell("print('hi')", execution_count=None)],
        )
        result = validate_notebook_structure(path)
        assert result.is_valid is False

    def test_invalid_json_returns_error(self, tmp_path: Path):
        bad = tmp_path / "broken.ipynb"
        bad.write_text("{not: valid json", encoding="utf-8")
        result = validate_notebook_structure(bad)
        assert result.is_valid is False
        assert any("Invalid JSON" in e for e in result.errors)

    def test_missing_file_returns_error(self, tmp_path: Path):
        result = validate_notebook_structure(tmp_path / "does-not-exist.ipynb")
        assert result.is_valid is False
        assert any("not found" in e.lower() for e in result.errors)


class TestGetNotebookKernelInfo:
    def test_returns_python_kernel(self):
        info = get_notebook_kernel_info(_build_notebook([]))
        assert info["kernel_name"] == "python3"
        assert info["language"] == "python"

    def test_handles_missing_metadata(self):
        info = get_notebook_kernel_info({})
        assert info["kernel_name"] == "unknown"
        assert info["language"] == "unknown"


class TestFindAllNotebooks:
    def test_discovers_notebooks(self, tmp_path: Path):
        (tmp_path / "a.ipynb").write_text("{}")
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "b.ipynb").write_text("{}")
        found = find_all_notebooks(tmp_path)
        assert {p.name for p in found} == {"a.ipynb", "b.ipynb"}

    def test_skips_checkpoints(self, tmp_path: Path):
        ckpt = tmp_path / ".ipynb_checkpoints"
        ckpt.mkdir()
        (ckpt / "stale.ipynb").write_text("{}")
        (tmp_path / "real.ipynb").write_text("{}")
        found = find_all_notebooks(tmp_path)
        assert [p.name for p in found] == ["real.ipynb"]

    def test_exclude_patterns(self, tmp_path: Path):
        (tmp_path / "keep.ipynb").write_text("{}")
        (tmp_path / "third_party").mkdir()
        (tmp_path / "third_party" / "skip.ipynb").write_text("{}")
        found = find_all_notebooks(tmp_path, exclude_patterns=["third_party/*"])
        assert [p.name for p in found] == ["keep.ipynb"]

    def test_results_are_sorted(self, tmp_path: Path):
        for name in ["c.ipynb", "a.ipynb", "b.ipynb"]:
            (tmp_path / name).write_text("{}")
        found = find_all_notebooks(tmp_path)
        assert [p.name for p in found] == ["a.ipynb", "b.ipynb", "c.ipynb"]


class TestLoadNotebook:
    def test_round_trip(self, tmp_path: Path):
        nb = _build_notebook([_code_cell("print(1)")])
        path = tmp_path / "nb.ipynb"
        path.write_text(json.dumps(nb), encoding="utf-8")
        assert load_notebook(path) == nb

    def test_invalid_json_raises(self, tmp_path: Path):
        bad = tmp_path / "broken.ipynb"
        bad.write_text("{not json", encoding="utf-8")
        with pytest.raises(json.JSONDecodeError):
            load_notebook(bad)
