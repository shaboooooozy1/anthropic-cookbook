"""Regression tests for ``scripts/validate_all_notebooks.py``'s auto-fix path.

``fix_deprecated_models`` previously tracked a single ``modified`` flag across
the whole notebook instead of per-cell. Once any cell matched a deprecated
model id, every later code cell got unconditionally overwritten with
``cell["source"] = new_source`` -- and for cells whose ``source`` was a plain
string (a valid nbformat representation, not just a list of lines), the
per-character iteration silently rewrote unrelated code into a list of
single-character "lines", destroying the cell content. These tests pin the
fixed per-cell behavior for both ``source`` representations.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# scripts/ is not a package, so add it to sys.path for import.
SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import validate_all_notebooks  # noqa: E402


def write_notebook(path: Path, cells: list[dict]) -> Path:
    nb = {
        "cells": cells,
        "metadata": {"kernelspec": {"name": "python3", "language": "python"}},
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    path.write_text(json.dumps(nb), encoding="utf-8")
    return path


def code_cell(source) -> dict:
    return {"cell_type": "code", "execution_count": 1, "source": source, "outputs": []}


def make_validator(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return validate_all_notebooks.NotebookValidator()


def test_fix_deprecated_models_replaces_list_source(tmp_path, monkeypatch):
    validator = make_validator(tmp_path, monkeypatch)
    nb_path = write_notebook(
        tmp_path / "nb.ipynb",
        [code_cell(['model = "claude-opus-4-1"\n'])],
    )

    assert validator.fix_deprecated_models(nb_path) is True

    nb = json.loads(nb_path.read_text())
    assert nb["cells"][0]["source"] == ['model = "claude-opus-4-6"\n']


def test_fix_deprecated_models_replaces_string_source(tmp_path, monkeypatch):
    validator = make_validator(tmp_path, monkeypatch)
    nb_path = write_notebook(
        tmp_path / "nb.ipynb",
        [code_cell('model = "claude-opus-4-1"')],
    )

    assert validator.fix_deprecated_models(nb_path) is True

    nb = json.loads(nb_path.read_text())
    assert nb["cells"][0]["source"] == 'model = "claude-opus-4-6"'


def test_fix_deprecated_models_does_not_corrupt_later_string_cell(tmp_path, monkeypatch):
    """A later unrelated cell with string-typed source must survive untouched.

    Regression test for the bug described in the module docstring: only the
    matching cell should be modified, and a plain-string ``source`` must never
    be exploded into a list of single characters.
    """
    validator = make_validator(tmp_path, monkeypatch)
    unrelated_source = "import re\n\n\ndef calculate(expression):\n    return eval(expression)"
    nb_path = write_notebook(
        tmp_path / "nb.ipynb",
        [
            code_cell(['model = "claude-opus-4-1"\n']),
            code_cell(unrelated_source),
        ],
    )

    assert validator.fix_deprecated_models(nb_path) is True

    nb = json.loads(nb_path.read_text())
    assert nb["cells"][0]["source"] == ['model = "claude-opus-4-6"\n']
    # The unrelated cell keeps its original string type and full content --
    # it must not be split into single-character list entries.
    assert nb["cells"][1]["source"] == unrelated_source


def test_fix_deprecated_models_no_match_returns_false(tmp_path, monkeypatch):
    validator = make_validator(tmp_path, monkeypatch)
    nb_path = write_notebook(
        tmp_path / "nb.ipynb",
        [code_cell('model = "claude-sonnet-4-6"')],
    )

    assert validator.fix_deprecated_models(nb_path) is False
    nb = json.loads(nb_path.read_text())
    assert nb["cells"][0]["source"] == 'model = "claude-sonnet-4-6"'
