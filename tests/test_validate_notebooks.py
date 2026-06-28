"""Tests for ``scripts/validate_notebooks.py`` — the pre-commit notebook linter.

This script runs on every commit via the pre-commit hook, so a regression here
breaks every contributor's workflow. The tests build minimal notebooks on disk
and drive ``main()`` via ``monkeypatch``/``capsys`` so we can assert exit codes
without invoking Jupyter.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# scripts/ is not a package, so add it to sys.path for import.
SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import validate_notebooks  # noqa: E402


def write_notebook(path: Path, cells: list[dict]) -> Path:
    """Write a minimal nbformat-4 notebook with the given cells."""
    nb = {
        "cells": cells,
        "metadata": {"kernelspec": {"name": "python3", "language": "python"}},
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(nb), encoding="utf-8")
    return path


def code_cell(source: str, outputs: list[dict] | None = None) -> dict:
    return {
        "cell_type": "code",
        "execution_count": 1,
        "source": source,
        "outputs": outputs or [],
        "metadata": {},
    }


def md_cell(source: str) -> dict:
    return {"cell_type": "markdown", "source": source, "metadata": {}}


class TestValidateNotebook:
    def test_clean_notebook_has_no_issues(self, tmp_path: Path):
        nb = write_notebook(tmp_path / "clean.ipynb", [code_cell("print(1)"), md_cell("# Title")])
        assert validate_notebooks.validate_notebook(nb) == []

    def test_empty_cell_flagged(self, tmp_path: Path):
        nb = write_notebook(tmp_path / "empty.ipynb", [code_cell("")])
        issues = validate_notebooks.validate_notebook(nb)
        assert len(issues) == 1
        assert "Empty cell" in issues[0]
        assert "Cell 0" in issues[0]

    def test_error_output_flagged(self, tmp_path: Path):
        cell = code_cell(
            "1/0",
            outputs=[{"output_type": "error", "ename": "ZeroDivisionError", "evalue": "x"}],
        )
        nb = write_notebook(tmp_path / "err.ipynb", [cell])
        issues = validate_notebooks.validate_notebook(nb)
        assert any("error output" in i for i in issues)

    def test_error_output_only_checked_for_code_cells(self, tmp_path: Path):
        # A stream output on a code cell is fine; only output_type == "error" trips.
        cell = code_cell("print('hi')", outputs=[{"output_type": "stream", "text": "hi"}])
        nb = write_notebook(tmp_path / "stream.ipynb", [cell])
        assert validate_notebooks.validate_notebook(nb) == []

    def test_reports_both_empty_and_error(self, tmp_path: Path):
        empty = code_cell("")
        bad = code_cell("boom", outputs=[{"output_type": "error", "ename": "E", "evalue": "v"}])
        nb = write_notebook(tmp_path / "both.ipynb", [empty, bad])
        issues = validate_notebooks.validate_notebook(nb)
        # One empty-cell issue (cell 0) + one error-output issue (cell 1).
        assert len(issues) == 2


class TestMain:
    def test_no_notebooks_exits_zero(self, monkeypatch, capsys):
        monkeypatch.setattr(sys, "argv", ["validate_notebooks.py"])
        with pytest.raises(SystemExit) as exc:
            validate_notebooks.main()
        assert exc.value.code == 0
        assert "No notebooks" in capsys.readouterr().out

    def test_all_discovers_notebooks_from_current_directory(
        self, tmp_path: Path, monkeypatch, capsys
    ):
        write_notebook(tmp_path / "clean.ipynb", [code_cell("print(1)")])
        write_notebook(tmp_path / "nested" / "other.ipynb", [code_cell("print(2)")])
        checkpoint_dir = tmp_path / ".ipynb_checkpoints"
        checkpoint_dir.mkdir()
        write_notebook(checkpoint_dir / "ignored.ipynb", [code_cell("")])

        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(sys, "argv", ["validate_notebooks.py", "--all"])
        with pytest.raises(SystemExit) as exc:
            validate_notebooks.main()

        assert exc.value.code == 0
        assert "All 2 notebook(s) validated successfully" in capsys.readouterr().out

    def test_clean_notebook_exits_zero(self, tmp_path: Path, monkeypatch, capsys):
        nb = write_notebook(tmp_path / "clean.ipynb", [code_cell("print(1)")])
        monkeypatch.setattr(sys, "argv", ["validate_notebooks.py", str(nb)])
        with pytest.raises(SystemExit) as exc:
            validate_notebooks.main()
        assert exc.value.code == 0
        assert "validated successfully" in capsys.readouterr().out

    def test_dirty_notebook_exits_one(self, tmp_path: Path, monkeypatch, capsys):
        nb = write_notebook(tmp_path / "dirty.ipynb", [code_cell("")])
        monkeypatch.setattr(sys, "argv", ["validate_notebooks.py", str(nb)])
        with pytest.raises(SystemExit) as exc:
            validate_notebooks.main()
        assert exc.value.code == 1
        out = capsys.readouterr().out
        assert "must be fixed" in out

    def test_non_notebook_args_ignored(self, tmp_path: Path, monkeypatch, capsys):
        # A .py argument is filtered out; with nothing left we exit 0.
        monkeypatch.setattr(sys, "argv", ["validate_notebooks.py", "foo.py", "README.md"])
        with pytest.raises(SystemExit) as exc:
            validate_notebooks.main()
        assert exc.value.code == 0
