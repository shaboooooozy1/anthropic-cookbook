"""Unit tests for notebook validation utilities."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from tests.notebook_tests import utils
from tests.notebook_tests.utils import CellInfo


def _cell(
    index: int,
    cell_type: str = "code",
    source: str = "print('hello')",
    execution_count: int | None = 1,
    outputs: list[dict] | None = None,
) -> CellInfo:
    outputs = outputs or []
    return CellInfo(
        index=index,
        cell_type=cell_type,
        execution_count=execution_count,
        source=source,
        outputs=outputs,
        has_error_output=any(output.get("output_type") == "error" for output in outputs),
        is_empty=not source.strip(),
    )


def _write_notebook(path: Path, cells: list[dict]) -> None:
    path.write_text(
        json.dumps(
            {
                "cells": cells,
                "metadata": {
                    "kernelspec": {
                        "name": "python3",
                        "display_name": "Python 3",
                        "language": "python",
                    },
                    "language_info": {"name": "python", "version": "3.11.0"},
                },
                "nbformat": 4,
                "nbformat_minor": 5,
            }
        ),
        encoding="utf-8",
    )


def test_load_and_parse_notebook_cells(tmp_path: Path) -> None:
    notebook_path = tmp_path / "example.ipynb"
    _write_notebook(
        notebook_path,
        [
            {"cell_type": "markdown", "source": ["# Title"]},
            {
                "cell_type": "code",
                "source": ["raise ValueError('bad')"],
                "execution_count": 2,
                "outputs": [{"output_type": "error", "ename": "ValueError", "evalue": "bad"}],
            },
            {"cell_type": "code", "source": [], "execution_count": None, "outputs": []},
        ],
    )

    notebook = utils.load_notebook(notebook_path)
    cells = utils.parse_notebook_cells(notebook)

    assert [cell.cell_type for cell in cells] == ["markdown", "code", "code"]
    assert cells[1].source == "raise ValueError('bad')"
    assert cells[1].has_error_output is True
    assert cells[2].is_empty is True


def test_validate_cell_execution_order_accepts_sequential_cells() -> None:
    cells = [_cell(0, execution_count=1), _cell(1, execution_count=2)]

    assert utils.validate_cell_execution_order(cells) == []


def test_validate_cell_execution_order_reports_out_of_order_and_gaps() -> None:
    cells = [
        _cell(0, execution_count=1),
        _cell(1, execution_count=3),
        _cell(2, execution_count=2),
    ]

    issues = utils.validate_cell_execution_order(cells)

    assert any("Non-sequential execution" in issue for issue in issues)
    assert any("Cells executed out of order" in issue for issue in issues)


def test_validate_all_cells_executed_ignores_empty_code_and_non_code_cells() -> None:
    cells = [
        _cell(0, execution_count=None),
        _cell(1, source="", execution_count=None),
        _cell(2, cell_type="markdown", source="notes", execution_count=None),
    ]

    assert utils.validate_all_cells_executed(cells) == [
        "Cell 0: Code cell has not been executed"
    ]


def test_validate_no_error_outputs_includes_error_details() -> None:
    cells = [
        _cell(
            0,
            outputs=[{"output_type": "error", "ename": "RuntimeError", "evalue": "boom"}],
        )
    ]

    assert utils.validate_no_error_outputs(cells) == [
        "Cell 0: Error output - RuntimeError: boom"
    ]


def test_validate_no_empty_cells_reports_all_empty_cell_types() -> None:
    cells = [
        _cell(0, source=""),
        _cell(1, cell_type="markdown", source="", execution_count=None),
    ]

    assert utils.validate_no_empty_cells(cells) == [
        "Cell 0: Empty code cell",
        "Cell 1: Empty markdown cell",
    ]


def test_validate_no_hardcoded_secrets_detects_keys_and_env_assignments() -> None:
    cells = [
        _cell(0, source='api_key = "sk-ant-not-a-real-key"'),
        _cell(1, source='os.environ["ANTHROPIC_API_KEY"] = "not-a-real-secret"'),
        _cell(2, cell_type="markdown", source="sk-ant-doc-example", execution_count=None),
    ]

    issues = utils.validate_no_hardcoded_secrets(cells)

    assert len(issues) == 2
    assert all("Possible hardcoded API key" in issue for issue in issues)


def test_extract_pip_dependencies_handles_flags_versions_and_extras() -> None:
    cells = [
        _cell(
            0,
            source=(
                "%pip install -q anthropic>=0.71 pandas[excel]==2.0\n"
                "!pip install --quiet rich"
            ),
        )
    ]

    assert set(utils.extract_pip_dependencies(cells)) == {"anthropic", "pandas", "rich"}


def test_validate_notebook_structure_collects_errors_and_warnings(tmp_path: Path) -> None:
    notebook_path = tmp_path / "problem.ipynb"
    _write_notebook(
        notebook_path,
        [
            {
                "cell_type": "code",
                "source": ["print('first')"],
                "execution_count": 2,
                "outputs": [],
            },
            {
                "cell_type": "code",
                "source": [],
                "execution_count": None,
                "outputs": [],
            },
            {
                "cell_type": "code",
                "source": ["print('second')"],
                "execution_count": None,
                "outputs": [{"output_type": "error", "ename": "NameError", "evalue": "missing"}],
            },
        ],
    )

    result = utils.validate_notebook_structure(notebook_path)

    assert result.is_valid is False
    assert any("Code cell has not been executed" in error for error in result.errors)
    assert any("Error output - NameError: missing" in error for error in result.errors)
    assert result.warnings == ["Cell 1: Empty code cell"]
    assert len(result.cells) == 3


def test_validate_notebook_structure_handles_invalid_json_and_missing_file(tmp_path: Path) -> None:
    invalid_path = tmp_path / "invalid.ipynb"
    invalid_path.write_text("{", encoding="utf-8")

    invalid_result = utils.validate_notebook_structure(invalid_path)
    missing_result = utils.validate_notebook_structure(tmp_path / "missing.ipynb")

    assert invalid_result.is_valid is False
    assert invalid_result.errors[0].startswith("Invalid JSON:")
    assert missing_result.is_valid is False
    assert missing_result.errors == [f"File not found: {tmp_path / 'missing.ipynb'}"]


def test_get_notebook_kernel_info_uses_kernelspec_with_language_info_fallback() -> None:
    notebook = {
        "metadata": {
            "kernelspec": {"name": "python3", "display_name": "Python 3"},
            "language_info": {"name": "python", "version": "3.12.0"},
        }
    }

    assert utils.get_notebook_kernel_info(notebook) == {
        "kernel_name": "python3",
        "kernel_display_name": "Python 3",
        "language": "python",
        "language_version": "3.12.0",
    }


def test_find_all_notebooks_sorts_results_and_applies_excludes(tmp_path: Path) -> None:
    first = tmp_path / "a.ipynb"
    second = tmp_path / "nested" / "b.ipynb"
    checkpoint = tmp_path / ".ipynb_checkpoints" / "ignored.ipynb"
    third_party = tmp_path / "third_party" / "integration.ipynb"

    for path in [second, first, checkpoint, third_party]:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}", encoding="utf-8")

    notebooks = utils.find_all_notebooks(tmp_path, exclude_patterns=["third_party/*"])

    assert notebooks == [first, second]


def test_execute_notebook_success_builds_expected_command(monkeypatch, tmp_path: Path) -> None:
    notebook_path = tmp_path / "example.ipynb"
    notebook_path.write_text("{}", encoding="utf-8")
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")

    monkeypatch.setattr(utils.subprocess, "run", fake_run)

    success, message, output_path = utils.execute_notebook(
        notebook_path,
        timeout=5,
        kernel_name="python3",
        allow_errors=True,
    )

    assert success is True
    assert message == "Notebook executed successfully"
    assert output_path is not None
    assert "--allow-errors" in calls[0][0]
    assert "--ExecutePreprocessor.kernel_name=python3" in calls[0][0]
    assert calls[0][0][-1] == str(notebook_path)
    assert calls[0][1]["timeout"] == 35
    output_path.unlink()


def test_execute_notebook_reports_failure(monkeypatch, tmp_path: Path) -> None:
    notebook_path = tmp_path / "example.ipynb"
    notebook_path.write_text("{}", encoding="utf-8")

    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="failed")

    monkeypatch.setattr(utils.subprocess, "run", fake_run)

    success, message, output_path = utils.execute_notebook(notebook_path)

    assert success is False
    assert message == "Execution failed: failed"
    assert output_path is not None
    output_path.unlink()


def test_execute_notebook_reports_timeout(monkeypatch, tmp_path: Path) -> None:
    notebook_path = tmp_path / "example.ipynb"
    notebook_path.write_text("{}", encoding="utf-8")

    def fake_run(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, timeout=kwargs["timeout"])

    monkeypatch.setattr(utils.subprocess, "run", fake_run)

    success, message, output_path = utils.execute_notebook(notebook_path, timeout=1)

    assert success is False
    assert message == "Execution timed out after 1 seconds"
    assert output_path is None
