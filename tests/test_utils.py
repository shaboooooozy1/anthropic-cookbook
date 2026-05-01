"""Unit tests for tests/notebook_tests/utils.py."""

from __future__ import annotations

import json
import tempfile
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
    validate_uses_env_for_api_key,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_cell(
    cell_type: str = "code",
    source: str = "print('hello')",
    execution_count: int | None = 1,
    outputs: list | None = None,
) -> dict:
    """Build a minimal notebook cell dict."""
    cell: dict = {"cell_type": cell_type, "source": source}
    if cell_type == "code":
        cell["execution_count"] = execution_count
        cell["outputs"] = outputs if outputs is not None else []
    return cell


def _make_notebook(cells: list[dict], kernel_name: str = "python3") -> dict:
    """Build a minimal notebook dict."""
    return {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": kernel_name,
            },
            "language_info": {"name": "python", "version": "3.11.0"},
        },
        "cells": cells,
    }


def _write_notebook(nb: dict, path: Path) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(nb, f)


# ---------------------------------------------------------------------------
# CellInfo
# ---------------------------------------------------------------------------


class TestCellInfo:
    def test_basic_creation(self):
        cell = CellInfo(
            index=0,
            cell_type="code",
            execution_count=1,
            source="x = 1",
            outputs=[],
        )
        assert cell.index == 0
        assert cell.cell_type == "code"
        assert cell.execution_count == 1
        assert cell.source == "x = 1"
        assert cell.outputs == []
        assert cell.has_error_output is False
        assert cell.is_empty is False

    def test_defaults(self):
        cell = CellInfo(index=1, cell_type="markdown", execution_count=None, source="", outputs=[])
        assert cell.has_error_output is False
        assert cell.is_empty is False

    def test_with_error_and_empty(self):
        cell = CellInfo(
            index=2,
            cell_type="code",
            execution_count=None,
            source="",
            outputs=[],
            has_error_output=True,
            is_empty=True,
        )
        assert cell.has_error_output is True
        assert cell.is_empty is True


# ---------------------------------------------------------------------------
# NotebookValidationResult
# ---------------------------------------------------------------------------


class TestNotebookValidationResult:
    def test_initial_state(self, tmp_path):
        path = tmp_path / "nb.ipynb"
        result = NotebookValidationResult(path=path)
        assert result.is_valid is True
        assert result.errors == []
        assert result.warnings == []
        assert result.info == []
        assert result.cells == []

    def test_add_error_marks_invalid(self, tmp_path):
        result = NotebookValidationResult(path=tmp_path / "nb.ipynb")
        result.add_error("something broke")
        assert result.is_valid is False
        assert "something broke" in result.errors

    def test_add_warning_keeps_valid(self, tmp_path):
        result = NotebookValidationResult(path=tmp_path / "nb.ipynb")
        result.add_warning("mild concern")
        assert result.is_valid is True
        assert "mild concern" in result.warnings

    def test_add_info(self, tmp_path):
        result = NotebookValidationResult(path=tmp_path / "nb.ipynb")
        result.add_info("note this")
        assert "note this" in result.info

    def test_multiple_errors(self, tmp_path):
        result = NotebookValidationResult(path=tmp_path / "nb.ipynb")
        result.add_error("err1")
        result.add_error("err2")
        assert len(result.errors) == 2
        assert result.is_valid is False


# ---------------------------------------------------------------------------
# load_notebook
# ---------------------------------------------------------------------------


class TestLoadNotebook:
    def test_loads_valid_notebook(self, tmp_path):
        nb = _make_notebook([_make_cell()])
        path = tmp_path / "test.ipynb"
        _write_notebook(nb, path)
        loaded = load_notebook(path)
        assert loaded["nbformat"] == 4

    def test_raises_on_invalid_json(self, tmp_path):
        path = tmp_path / "bad.ipynb"
        path.write_text("not json", encoding="utf-8")
        with pytest.raises(json.JSONDecodeError):
            load_notebook(path)

    def test_raises_on_missing_file(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_notebook(tmp_path / "missing.ipynb")


# ---------------------------------------------------------------------------
# parse_notebook_cells
# ---------------------------------------------------------------------------


class TestParseNotebookCells:
    def test_basic_code_cell(self):
        nb = _make_notebook([_make_cell(source="x = 1", execution_count=1)])
        cells = parse_notebook_cells(nb)
        assert len(cells) == 1
        assert cells[0].cell_type == "code"
        assert cells[0].source == "x = 1"
        assert cells[0].execution_count == 1
        assert cells[0].is_empty is False

    def test_empty_cell_flagged(self):
        nb = _make_notebook([_make_cell(source="   ", execution_count=1)])
        cells = parse_notebook_cells(nb)
        assert cells[0].is_empty is True

    def test_completely_empty_source(self):
        nb = _make_notebook([_make_cell(source="", execution_count=1)])
        cells = parse_notebook_cells(nb)
        assert cells[0].is_empty is True

    def test_error_output_detected(self):
        outputs = [{"output_type": "error", "ename": "ValueError", "evalue": "bad", "traceback": []}]
        nb = _make_notebook([_make_cell(outputs=outputs, execution_count=1)])
        cells = parse_notebook_cells(nb)
        assert cells[0].has_error_output is True

    def test_no_error_output(self):
        outputs = [{"output_type": "stream", "name": "stdout", "text": "hi"}]
        nb = _make_notebook([_make_cell(outputs=outputs, execution_count=1)])
        cells = parse_notebook_cells(nb)
        assert cells[0].has_error_output is False

    def test_markdown_cell(self):
        cell = {"cell_type": "markdown", "source": "# Title"}
        nb = _make_notebook([cell])
        cells = parse_notebook_cells(nb)
        assert cells[0].cell_type == "markdown"
        assert cells[0].execution_count is None

    def test_source_as_list_joined(self):
        cell = _make_cell()
        cell["source"] = ["line1\n", "line2"]
        nb = _make_notebook([cell])
        cells = parse_notebook_cells(nb)
        assert cells[0].source == "line1\nline2"

    def test_multiple_cells_indexed(self):
        nb = _make_notebook([
            _make_cell(source="a = 1", execution_count=1),
            _make_cell(source="b = 2", execution_count=2),
        ])
        cells = parse_notebook_cells(nb)
        assert cells[0].index == 0
        assert cells[1].index == 1

    def test_empty_notebook(self):
        nb = _make_notebook([])
        cells = parse_notebook_cells(nb)
        assert cells == []


# ---------------------------------------------------------------------------
# validate_cell_execution_order
# ---------------------------------------------------------------------------


class TestValidateCellExecutionOrder:
    def _cells(self, counts):
        return [
            CellInfo(index=i, cell_type="code", execution_count=c, source="x", outputs=[])
            for i, c in enumerate(counts)
        ]

    def test_sequential_no_issues(self):
        cells = self._cells([1, 2, 3, 4])
        assert validate_cell_execution_order(cells) == []

    def test_out_of_order_detected(self):
        cells = self._cells([1, 3, 2])
        issues = validate_cell_execution_order(cells)
        assert len(issues) > 0

    def test_gap_detected(self):
        cells = self._cells([1, 3])
        issues = validate_cell_execution_order(cells)
        assert len(issues) > 0

    def test_none_counts_skipped(self):
        cells = self._cells([None, None])
        assert validate_cell_execution_order(cells) == []

    def test_mixed_none_and_sequential(self):
        cells = [
            CellInfo(index=0, cell_type="code", execution_count=None, source="x", outputs=[]),
            CellInfo(index=1, cell_type="code", execution_count=1, source="y", outputs=[]),
            CellInfo(index=2, cell_type="code", execution_count=2, source="z", outputs=[]),
        ]
        assert validate_cell_execution_order(cells) == []

    def test_single_cell(self):
        cells = self._cells([1])
        assert validate_cell_execution_order(cells) == []

    def test_markdown_cells_ignored(self):
        cells = [
            CellInfo(index=0, cell_type="markdown", execution_count=None, source="# h", outputs=[]),
            CellInfo(index=1, cell_type="code", execution_count=1, source="x", outputs=[]),
            CellInfo(index=2, cell_type="code", execution_count=2, source="y", outputs=[]),
        ]
        assert validate_cell_execution_order(cells) == []

    def test_empty_list(self):
        assert validate_cell_execution_order([]) == []


# ---------------------------------------------------------------------------
# validate_all_cells_executed
# ---------------------------------------------------------------------------


class TestValidateAllCellsExecuted:
    def test_all_executed(self):
        cells = [
            CellInfo(index=0, cell_type="code", execution_count=1, source="x=1", outputs=[]),
            CellInfo(index=1, cell_type="code", execution_count=2, source="y=2", outputs=[]),
        ]
        assert validate_all_cells_executed(cells) == []

    def test_unexecuted_detected(self):
        cells = [
            CellInfo(index=0, cell_type="code", execution_count=None, source="x=1", outputs=[]),
        ]
        issues = validate_all_cells_executed(cells)
        assert len(issues) == 1
        assert "0" in issues[0]

    def test_empty_cells_skipped(self):
        cells = [
            CellInfo(
                index=0,
                cell_type="code",
                execution_count=None,
                source="",
                outputs=[],
                is_empty=True,
            ),
        ]
        assert validate_all_cells_executed(cells) == []

    def test_markdown_cells_skipped(self):
        cells = [
            CellInfo(
                index=0, cell_type="markdown", execution_count=None, source="# h", outputs=[]
            ),
        ]
        assert validate_all_cells_executed(cells) == []

    def test_empty_list(self):
        assert validate_all_cells_executed([]) == []


# ---------------------------------------------------------------------------
# validate_no_error_outputs
# ---------------------------------------------------------------------------


class TestValidateNoErrorOutputs:
    def test_no_errors(self):
        cells = [
            CellInfo(
                index=0,
                cell_type="code",
                execution_count=1,
                source="x=1",
                outputs=[{"output_type": "stream", "text": "hi"}],
                has_error_output=False,
            ),
        ]
        assert validate_no_error_outputs(cells) == []

    def test_error_detected(self):
        error_output = {
            "output_type": "error",
            "ename": "ValueError",
            "evalue": "something went wrong",
            "traceback": [],
        }
        cells = [
            CellInfo(
                index=2,
                cell_type="code",
                execution_count=3,
                source="raise ValueError()",
                outputs=[error_output],
                has_error_output=True,
            ),
        ]
        issues = validate_no_error_outputs(cells)
        assert len(issues) == 1
        assert "ValueError" in issues[0]
        assert "2" in issues[0]

    def test_multiple_errors(self):
        error_out = {"output_type": "error", "ename": "E", "evalue": "v", "traceback": []}
        cells = [
            CellInfo(
                index=i,
                cell_type="code",
                execution_count=i + 1,
                source="x",
                outputs=[error_out],
                has_error_output=True,
            )
            for i in range(3)
        ]
        issues = validate_no_error_outputs(cells)
        assert len(issues) == 3

    def test_empty_list(self):
        assert validate_no_error_outputs([]) == []


# ---------------------------------------------------------------------------
# validate_no_empty_cells
# ---------------------------------------------------------------------------


class TestValidateNoEmptyCells:
    def test_no_empty_cells(self):
        cells = [
            CellInfo(index=0, cell_type="code", execution_count=1, source="x=1", outputs=[]),
        ]
        assert validate_no_empty_cells(cells) == []

    def test_empty_code_cell_warned(self):
        cells = [
            CellInfo(
                index=0,
                cell_type="code",
                execution_count=None,
                source="",
                outputs=[],
                is_empty=True,
            ),
        ]
        warnings = validate_no_empty_cells(cells)
        assert len(warnings) == 1
        assert "0" in warnings[0]

    def test_empty_markdown_cell_warned(self):
        cells = [
            CellInfo(
                index=1,
                cell_type="markdown",
                execution_count=None,
                source="",
                outputs=[],
                is_empty=True,
            ),
        ]
        warnings = validate_no_empty_cells(cells)
        assert len(warnings) == 1

    def test_empty_list(self):
        assert validate_no_empty_cells([]) == []


# ---------------------------------------------------------------------------
# validate_no_hardcoded_secrets
# ---------------------------------------------------------------------------


class TestValidateNoHardcodedSecrets:
    def test_clean_code(self):
        cells = [
            CellInfo(
                index=0,
                cell_type="code",
                execution_count=1,
                source='client = anthropic.Anthropic()',
                outputs=[],
            ),
        ]
        assert validate_no_hardcoded_secrets(cells) == []

    def test_anthropic_key_pattern_detected(self):
        cells = [
            CellInfo(
                index=0,
                cell_type="code",
                execution_count=1,
                source='api_key = "sk-ant-api03-realkey1234567890abcdefghij"',
                outputs=[],
            ),
        ]
        issues = validate_no_hardcoded_secrets(cells)
        assert len(issues) == 1
        assert "0" in issues[0]

    def test_hardcoded_assignment_pattern_detected(self):
        cells = [
            CellInfo(
                index=1,
                cell_type="code",
                execution_count=2,
                source='"ANTHROPIC_API_KEY" = "my-secret-key"',
                outputs=[],
            ),
        ]
        issues = validate_no_hardcoded_secrets(cells)
        assert len(issues) >= 1

    def test_env_var_usage_not_flagged(self):
        cells = [
            CellInfo(
                index=0,
                cell_type="code",
                execution_count=1,
                source='import os\napi_key = os.environ.get("ANTHROPIC_API_KEY")',
                outputs=[],
            ),
        ]
        assert validate_no_hardcoded_secrets(cells) == []

    def test_markdown_cells_skipped(self):
        cells = [
            CellInfo(
                index=0,
                cell_type="markdown",
                execution_count=None,
                source='sk-ant-api03-examplekey is a sample',
                outputs=[],
            ),
        ]
        assert validate_no_hardcoded_secrets(cells) == []

    def test_empty_list(self):
        assert validate_no_hardcoded_secrets([]) == []


# ---------------------------------------------------------------------------
# validate_uses_env_for_api_key
# ---------------------------------------------------------------------------


class TestValidateUsesEnvForApiKey:
    def test_uses_os_environ_get(self):
        cells = [
            CellInfo(
                index=0,
                cell_type="code",
                execution_count=1,
                source='import os\nkey = os.environ.get("ANTHROPIC_API_KEY")',
                outputs=[],
            ),
        ]
        # Should return no warnings
        warnings = validate_uses_env_for_api_key(cells)
        assert isinstance(warnings, list)

    def test_uses_os_getenv(self):
        cells = [
            CellInfo(
                index=0,
                cell_type="code",
                execution_count=1,
                source='key = os.getenv("ANTHROPIC_API_KEY")',
                outputs=[],
            ),
        ]
        warnings = validate_uses_env_for_api_key(cells)
        assert isinstance(warnings, list)

    def test_no_anthropic_import_no_warning(self):
        cells = [
            CellInfo(
                index=0,
                cell_type="code",
                execution_count=1,
                source="x = 1",
                outputs=[],
            ),
        ]
        warnings = validate_uses_env_for_api_key(cells)
        assert warnings == []

    def test_empty_list(self):
        assert validate_uses_env_for_api_key([]) == []


# ---------------------------------------------------------------------------
# extract_pip_dependencies
# ---------------------------------------------------------------------------


class TestExtractPipDependencies:
    def test_pip_magic_command(self):
        cells = [
            CellInfo(
                index=0,
                cell_type="code",
                execution_count=1,
                source="%pip install anthropic pandas",
                outputs=[],
            ),
        ]
        deps = extract_pip_dependencies(cells)
        assert "anthropic" in deps
        assert "pandas" in deps

    def test_pip_shell_command(self):
        cells = [
            CellInfo(
                index=0,
                cell_type="code",
                execution_count=1,
                source="!pip install numpy",
                outputs=[],
            ),
        ]
        deps = extract_pip_dependencies(cells)
        assert "numpy" in deps

    def test_pip_with_flags_ignored(self):
        cells = [
            CellInfo(
                index=0,
                cell_type="code",
                execution_count=1,
                source="%pip install -q requests",
                outputs=[],
            ),
        ]
        deps = extract_pip_dependencies(cells)
        assert "requests" in deps
        assert "-q" not in deps

    def test_package_with_version(self):
        cells = [
            CellInfo(
                index=0,
                cell_type="code",
                execution_count=1,
                source="%pip install anthropic==0.10.0",
                outputs=[],
            ),
        ]
        deps = extract_pip_dependencies(cells)
        assert "anthropic" in deps

    def test_package_with_extras(self):
        cells = [
            CellInfo(
                index=0,
                cell_type="code",
                execution_count=1,
                source="%pip install anthropic[bedrock]",
                outputs=[],
            ),
        ]
        deps = extract_pip_dependencies(cells)
        assert "anthropic" in deps

    def test_no_pip_commands(self):
        cells = [
            CellInfo(
                index=0,
                cell_type="code",
                execution_count=1,
                source="import os",
                outputs=[],
            ),
        ]
        assert extract_pip_dependencies(cells) == []

    def test_markdown_cells_skipped(self):
        cells = [
            CellInfo(
                index=0,
                cell_type="markdown",
                execution_count=None,
                source="%pip install something",
                outputs=[],
            ),
        ]
        assert extract_pip_dependencies(cells) == []

    def test_deduplication(self):
        cells = [
            CellInfo(
                index=0,
                cell_type="code",
                execution_count=1,
                source="%pip install anthropic\n%pip install anthropic",
                outputs=[],
            ),
        ]
        deps = extract_pip_dependencies(cells)
        assert deps.count("anthropic") == 1

    def test_empty_list(self):
        assert extract_pip_dependencies([]) == []


# ---------------------------------------------------------------------------
# get_notebook_kernel_info
# ---------------------------------------------------------------------------


class TestGetNotebookKernelInfo:
    def test_standard_python_kernel(self):
        nb = _make_notebook([])
        info = get_notebook_kernel_info(nb)
        assert info["kernel_name"] == "python3"
        assert info["language"] == "python"
        assert info["language_version"] == "3.11.0"

    def test_missing_metadata_defaults(self):
        nb = {"metadata": {}, "cells": []}
        info = get_notebook_kernel_info(nb)
        assert info["kernel_name"] == "unknown"
        assert info["language"] == "unknown"

    def test_language_from_language_info(self):
        nb = {
            "metadata": {
                "kernelspec": {},
                "language_info": {"name": "python", "version": "3.12"},
            },
            "cells": [],
        }
        info = get_notebook_kernel_info(nb)
        assert info["language"] == "python"

    def test_display_name(self):
        nb = _make_notebook([])
        info = get_notebook_kernel_info(nb)
        assert info["kernel_display_name"] == "Python 3"


# ---------------------------------------------------------------------------
# validate_notebook_structure
# ---------------------------------------------------------------------------


class TestValidateNotebookStructure:
    def test_valid_notebook_passes(self, tmp_path):
        nb = _make_notebook([
            _make_cell(source="x = 1", execution_count=1),
        ])
        path = tmp_path / "nb.ipynb"
        _write_notebook(nb, path)
        result = validate_notebook_structure(path)
        assert result.is_valid is True
        assert result.errors == []

    def test_invalid_json_fails(self, tmp_path):
        path = tmp_path / "bad.ipynb"
        path.write_text("{not json}", encoding="utf-8")
        result = validate_notebook_structure(path)
        assert result.is_valid is False
        assert any("JSON" in e for e in result.errors)

    def test_missing_file_fails(self, tmp_path):
        result = validate_notebook_structure(tmp_path / "ghost.ipynb")
        assert result.is_valid is False
        assert any("not found" in e.lower() or "File not found" in e for e in result.errors)

    def test_error_output_makes_invalid(self, tmp_path):
        error_out = {"output_type": "error", "ename": "RuntimeError", "evalue": "bad", "traceback": []}
        nb = _make_notebook([_make_cell(outputs=[error_out], execution_count=1)])
        path = tmp_path / "nb.ipynb"
        _write_notebook(nb, path)
        result = validate_notebook_structure(path)
        assert result.is_valid is False

    def test_hardcoded_key_makes_invalid(self, tmp_path):
        nb = _make_notebook([
            _make_cell(
                source='key = "sk-ant-api03-realkey1234567890abcdefghij"',
                execution_count=1,
            ),
        ])
        path = tmp_path / "nb.ipynb"
        _write_notebook(nb, path)
        result = validate_notebook_structure(path)
        assert result.is_valid is False

    def test_unexecuted_cell_makes_invalid(self, tmp_path):
        nb = _make_notebook([_make_cell(source="x = 1", execution_count=None)])
        path = tmp_path / "nb.ipynb"
        _write_notebook(nb, path)
        result = validate_notebook_structure(path)
        assert result.is_valid is False

    def test_result_has_path(self, tmp_path):
        nb = _make_notebook([_make_cell()])
        path = tmp_path / "nb.ipynb"
        _write_notebook(nb, path)
        result = validate_notebook_structure(path)
        assert result.path == path


# ---------------------------------------------------------------------------
# find_all_notebooks
# ---------------------------------------------------------------------------


class TestFindAllNotebooks:
    def test_finds_notebooks(self, tmp_path):
        nb = _make_notebook([_make_cell()])
        for name in ["a.ipynb", "b.ipynb"]:
            _write_notebook(nb, tmp_path / name)
        found = find_all_notebooks(tmp_path)
        assert len(found) == 2

    def test_skips_checkpoint_files(self, tmp_path):
        nb = _make_notebook([_make_cell()])
        checkpoint_dir = tmp_path / ".ipynb_checkpoints"
        checkpoint_dir.mkdir()
        _write_notebook(nb, checkpoint_dir / "test-checkpoint.ipynb")
        _write_notebook(nb, tmp_path / "real.ipynb")
        found = find_all_notebooks(tmp_path)
        assert len(found) == 1
        assert found[0].name == "real.ipynb"

    def test_recursive_search(self, tmp_path):
        nb = _make_notebook([_make_cell()])
        sub = tmp_path / "sub"
        sub.mkdir()
        _write_notebook(nb, sub / "nested.ipynb")
        found = find_all_notebooks(tmp_path)
        assert len(found) == 1

    def test_exclude_patterns(self, tmp_path):
        nb = _make_notebook([_make_cell()])
        third_party = tmp_path / "third_party"
        third_party.mkdir()
        _write_notebook(nb, third_party / "external.ipynb")
        _write_notebook(nb, tmp_path / "local.ipynb")
        found = find_all_notebooks(tmp_path, exclude_patterns=["third_party/*"])
        names = [f.name for f in found]
        assert "local.ipynb" in names
        assert "external.ipynb" not in names

    def test_returns_sorted(self, tmp_path):
        nb = _make_notebook([_make_cell()])
        _write_notebook(nb, tmp_path / "z.ipynb")
        _write_notebook(nb, tmp_path / "a.ipynb")
        found = find_all_notebooks(tmp_path)
        names = [f.name for f in found]
        assert names == sorted(names)

    def test_empty_directory(self, tmp_path):
        assert find_all_notebooks(tmp_path) == []

    def test_no_exclude_patterns(self, tmp_path):
        nb = _make_notebook([_make_cell()])
        _write_notebook(nb, tmp_path / "test.ipynb")
        found = find_all_notebooks(tmp_path, exclude_patterns=None)
        assert len(found) == 1
