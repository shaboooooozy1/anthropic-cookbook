"""Unit tests for tests/notebook_tests/utils.py.

The validators in utils.py are the safety net every notebook test relies on.
A bug there silently weakens every PR's structural check, so the pure-logic
helpers get table-driven coverage here.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.notebook_tests.utils import (
    CellInfo,
    NotebookValidationResult,
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


def _code_cell(index: int, source: str, execution_count: int | None = 1, outputs=None) -> CellInfo:
    outputs = outputs or []
    return CellInfo(
        index=index,
        cell_type="code",
        execution_count=execution_count,
        source=source,
        outputs=outputs,
        has_error_output=any(o.get("output_type") == "error" for o in outputs),
        is_empty=not source.strip(),
    )


def _markdown_cell(index: int, source: str = "# Title") -> CellInfo:
    return CellInfo(
        index=index,
        cell_type="markdown",
        execution_count=None,
        source=source,
        outputs=[],
    )


def _write_notebook(path: Path, cells: list[dict], metadata: dict | None = None) -> None:
    notebook = {
        "cells": cells,
        "metadata": metadata or {"kernelspec": {"name": "python3", "language": "python"}},
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    path.write_text(json.dumps(notebook), encoding="utf-8")


class TestParseNotebookCells:
    def test_empty_notebook(self):
        assert parse_notebook_cells({"cells": []}) == []

    def test_joins_multiline_source(self):
        cells = parse_notebook_cells(
            {"cells": [{"cell_type": "code", "source": ["line1\n", "line2\n"], "outputs": []}]}
        )
        assert cells[0].source == "line1\nline2\n"

    def test_marks_error_outputs(self):
        cells = parse_notebook_cells(
            {
                "cells": [
                    {
                        "cell_type": "code",
                        "source": ["x = 1"],
                        "outputs": [{"output_type": "error", "ename": "ValueError", "evalue": "x"}],
                    }
                ]
            }
        )
        assert cells[0].has_error_output is True

    def test_detects_empty_cell(self):
        cells = parse_notebook_cells(
            {"cells": [{"cell_type": "code", "source": ["   \n"], "outputs": []}]}
        )
        assert cells[0].is_empty is True

    def test_index_is_position_not_execution_count(self):
        cells = parse_notebook_cells(
            {
                "cells": [
                    {"cell_type": "markdown", "source": ["# h"]},
                    {
                        "cell_type": "code",
                        "source": ["x"],
                        "outputs": [],
                        "execution_count": 7,
                    },
                ]
            }
        )
        assert cells[1].index == 1
        assert cells[1].execution_count == 7


class TestValidateCellExecutionOrder:
    def test_in_order_passes(self):
        cells = [_code_cell(i, "x", execution_count=i + 1) for i in range(3)]
        assert validate_cell_execution_order(cells) == []

    def test_out_of_order_fails(self):
        cells = [
            _code_cell(0, "x", execution_count=1),
            _code_cell(1, "x", execution_count=3),
            _code_cell(2, "x", execution_count=2),
        ]
        issues = validate_cell_execution_order(cells)
        assert any("out of order" in i for i in issues)

    def test_gap_fails(self):
        cells = [
            _code_cell(0, "x", execution_count=1),
            _code_cell(1, "x", execution_count=3),
        ]
        issues = validate_cell_execution_order(cells)
        assert any("Non-sequential" in i for i in issues)

    def test_unexecuted_cells_ignored(self):
        cells = [
            _code_cell(0, "x", execution_count=None),
            _code_cell(1, "x", execution_count=None),
        ]
        assert validate_cell_execution_order(cells) == []

    def test_markdown_cells_ignored(self):
        cells = [
            _markdown_cell(0),
            _code_cell(1, "x", execution_count=1),
            _markdown_cell(2),
            _code_cell(3, "y", execution_count=2),
        ]
        assert validate_cell_execution_order(cells) == []


class TestValidateAllCellsExecuted:
    def test_all_executed_passes(self):
        cells = [_code_cell(0, "x", execution_count=1)]
        assert validate_all_cells_executed(cells) == []

    def test_unexecuted_cell_fails(self):
        cells = [_code_cell(0, "x", execution_count=None)]
        issues = validate_all_cells_executed(cells)
        assert len(issues) == 1
        assert "Cell 0" in issues[0]

    def test_empty_cell_skipped(self):
        cells = [_code_cell(0, "", execution_count=None)]
        assert validate_all_cells_executed(cells) == []

    def test_markdown_skipped(self):
        cells = [_markdown_cell(0)]
        assert validate_all_cells_executed(cells) == []


class TestValidateNoErrorOutputs:
    def test_no_outputs_passes(self):
        assert validate_no_error_outputs([_code_cell(0, "x")]) == []

    def test_error_output_fails(self):
        cell = _code_cell(
            0,
            "x",
            outputs=[{"output_type": "error", "ename": "ValueError", "evalue": "boom"}],
        )
        issues = validate_no_error_outputs([cell])
        assert len(issues) == 1
        assert "ValueError" in issues[0]
        assert "boom" in issues[0]

    def test_stream_output_passes(self):
        cell = _code_cell(0, "x", outputs=[{"output_type": "stream", "text": "ok"}])
        assert validate_no_error_outputs([cell]) == []


class TestValidateNoEmptyCells:
    def test_warns_for_empty(self):
        warnings = validate_no_empty_cells([_code_cell(0, "")])
        assert len(warnings) == 1


class TestValidateNoHardcodedSecrets:
    def test_clean_code_passes(self):
        cell = _code_cell(0, 'client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])')
        assert validate_no_hardcoded_secrets([cell]) == []

    def test_anthropic_key_pattern_fails(self):
        cell = _code_cell(0, 'api_key = "sk-ant-api03-ABCDEFGHIJKLMNOPQRSTUV"')
        issues = validate_no_hardcoded_secrets([cell])
        assert len(issues) == 1

    def test_inline_assignment_pattern_fails(self):
        cell = _code_cell(0, '"ANTHROPIC_API_KEY": "my-real-key-value"')
        issues = validate_no_hardcoded_secrets([cell])
        assert len(issues) == 1

    def test_markdown_cells_skipped(self):
        # Markdown explaining the format shouldn't trigger
        cell = _markdown_cell(0, "Your key looks like `sk-ant-api03-XXXXXXXXXX`")
        assert validate_no_hardcoded_secrets([cell]) == []

    def test_one_issue_per_cell_even_if_multiple_patterns_match(self):
        cell = _code_cell(0, 'k1 = "sk-ant-aaaaaaaa"\nk2 = "sk-ant-bbbbbbbb"')
        issues = validate_no_hardcoded_secrets([cell])
        # Function uses `break` after first match per cell
        assert len(issues) == 1


class TestExtractPipDependencies:
    @pytest.mark.parametrize(
        ("source", "expected"),
        [
            ("%pip install anthropic", {"anthropic"}),
            ("!pip install anthropic", {"anthropic"}),
            ("%pip install -q anthropic", {"anthropic"}),
            ("%pip install --quiet anthropic", {"anthropic"}),
            ("%pip install anthropic==0.71.0", {"anthropic"}),
            ("%pip install 'anthropic>=0.71.0'", {"'anthropic"}),  # documents quote handling
            ("%pip install anthropic[bedrock]", {"anthropic"}),
            ("%pip install anthropic openai voyageai", {"anthropic", "openai", "voyageai"}),
        ],
    )
    def test_parses_install_command(self, source, expected):
        cells = [_code_cell(0, source)]
        assert set(extract_pip_dependencies(cells)) == expected

    def test_dedupes_across_cells(self):
        cells = [
            _code_cell(0, "%pip install anthropic"),
            _code_cell(1, "%pip install anthropic"),
        ]
        assert extract_pip_dependencies(cells) == ["anthropic"]

    def test_markdown_cells_ignored(self):
        cells = [_markdown_cell(0, "Run `%pip install something`")]
        assert extract_pip_dependencies(cells) == []

    def test_no_install_returns_empty(self):
        cells = [_code_cell(0, "x = 1")]
        assert extract_pip_dependencies(cells) == []


class TestGetNotebookKernelInfo:
    def test_extracts_full_metadata(self):
        info = get_notebook_kernel_info(
            {
                "metadata": {
                    "kernelspec": {
                        "name": "python3",
                        "display_name": "Python 3",
                        "language": "python",
                    },
                    "language_info": {"name": "python", "version": "3.11.0"},
                }
            }
        )
        assert info["kernel_name"] == "python3"
        assert info["language"] == "python"
        assert info["language_version"] == "3.11.0"

    def test_falls_back_to_language_info(self):
        info = get_notebook_kernel_info(
            {"metadata": {"kernelspec": {}, "language_info": {"name": "python"}}}
        )
        assert info["language"] == "python"

    def test_returns_unknown_when_missing(self):
        info = get_notebook_kernel_info({"metadata": {}})
        assert info["kernel_name"] == "unknown"
        assert info["language"] == "unknown"


class TestFindAllNotebooks:
    def test_finds_notebooks_recursively(self, tmp_path: Path):
        (tmp_path / "a.ipynb").write_text("{}")
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "b.ipynb").write_text("{}")

        result = find_all_notebooks(tmp_path)
        names = {p.name for p in result}
        assert names == {"a.ipynb", "b.ipynb"}

    def test_skips_checkpoints(self, tmp_path: Path):
        (tmp_path / "a.ipynb").write_text("{}")
        ckpt = tmp_path / ".ipynb_checkpoints"
        ckpt.mkdir()
        (ckpt / "a-checkpoint.ipynb").write_text("{}")

        result = find_all_notebooks(tmp_path)
        assert [p.name for p in result] == ["a.ipynb"]

    def test_exclude_pattern(self, tmp_path: Path):
        (tmp_path / "third_party").mkdir()
        (tmp_path / "third_party" / "a.ipynb").write_text("{}")
        (tmp_path / "b.ipynb").write_text("{}")

        result = find_all_notebooks(tmp_path, exclude_patterns=["third_party/*"])
        assert [p.name for p in result] == ["b.ipynb"]

    def test_results_are_sorted(self, tmp_path: Path):
        for name in ["c.ipynb", "a.ipynb", "b.ipynb"]:
            (tmp_path / name).write_text("{}")

        result = find_all_notebooks(tmp_path)
        assert [p.name for p in result] == ["a.ipynb", "b.ipynb", "c.ipynb"]


class TestLoadAndValidateStructure:
    def test_load_notebook_roundtrip(self, tmp_path: Path):
        path = tmp_path / "nb.ipynb"
        _write_notebook(path, [{"cell_type": "code", "source": ["x"], "outputs": []}])
        data = load_notebook(path)
        assert data["nbformat"] == 4

    def test_invalid_json_recorded_as_error(self, tmp_path: Path):
        bad = tmp_path / "bad.ipynb"
        bad.write_text("not json", encoding="utf-8")
        result = validate_notebook_structure(bad)
        assert result.is_valid is False
        assert any("Invalid JSON" in e for e in result.errors)

    def test_missing_file_recorded_as_error(self, tmp_path: Path):
        result = validate_notebook_structure(tmp_path / "missing.ipynb")
        assert result.is_valid is False
        assert any("not found" in e.lower() for e in result.errors)

    def test_clean_notebook_passes(self, tmp_path: Path):
        path = tmp_path / "ok.ipynb"
        _write_notebook(
            path,
            [
                {"cell_type": "markdown", "source": ["# Demo"]},
                {
                    "cell_type": "code",
                    "source": ["x = 1"],
                    "outputs": [],
                    "execution_count": 1,
                },
            ],
        )
        result = validate_notebook_structure(path)
        assert result.is_valid is True, result.errors

    def test_hardcoded_key_marks_invalid(self, tmp_path: Path):
        path = tmp_path / "leaky.ipynb"
        _write_notebook(
            path,
            [
                {
                    "cell_type": "code",
                    "source": ['api_key = "sk-ant-api03-LEAKED-KEY-EXAMPLE"'],
                    "outputs": [],
                    "execution_count": 1,
                }
            ],
        )
        result = validate_notebook_structure(path)
        assert result.is_valid is False


class TestNotebookValidationResult:
    def test_add_error_flips_validity(self):
        r = NotebookValidationResult(path=Path("x"))
        assert r.is_valid is True
        r.add_error("boom")
        assert r.is_valid is False

    def test_add_warning_keeps_validity(self):
        r = NotebookValidationResult(path=Path("x"))
        r.add_warning("heads up")
        assert r.is_valid is True
