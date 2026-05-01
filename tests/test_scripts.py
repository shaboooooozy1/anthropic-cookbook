"""Unit tests for scripts/validate_notebooks.py and scripts/validate_authors_sorted.py."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"


def _import_script(name: str):
    """Import a script module from the scripts directory by file path."""
    spec = importlib.util.spec_from_file_location(name, _SCRIPTS_DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_validate_notebooks_mod = _import_script("validate_notebooks")
validate_notebook = _validate_notebooks_mod.validate_notebook

_validate_authors_mod = _import_script("validate_authors_sorted")
is_sorted = _validate_authors_mod.is_sorted
show_diff = _validate_authors_mod.show_diff
sort_authors = _validate_authors_mod.sort_authors


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_notebook(path: Path, cells: list[dict]) -> None:
    """Write a minimal notebook to disk."""
    nb = {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}
        },
        "cells": cells,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(nb, f)


def _code_cell(source: str, outputs: list | None = None) -> dict:
    return {
        "cell_type": "code",
        "source": source,
        "execution_count": 1,
        "outputs": outputs or [],
    }


def _markdown_cell(source: str) -> dict:
    return {"cell_type": "markdown", "source": source}


# ---------------------------------------------------------------------------
# validate_notebook()
# ---------------------------------------------------------------------------


class TestValidateNotebook:
    def test_valid_notebook_no_issues(self, tmp_path):
        path = tmp_path / "ok.ipynb"
        _write_notebook(path, [_code_cell("x = 1")])
        issues = validate_notebook(path)
        assert issues == []

    def test_empty_cell_reported(self, tmp_path):
        path = tmp_path / "empty.ipynb"
        _write_notebook(path, [_code_cell("")])
        issues = validate_notebook(path)
        assert len(issues) == 1
        assert "Empty cell" in issues[0]

    def test_empty_source_none_reported(self, tmp_path):
        """Cell with source=None (missing key) should be flagged."""
        nb = {
            "nbformat": 4,
            "nbformat_minor": 5,
            "metadata": {},
            "cells": [{"cell_type": "code", "outputs": [], "execution_count": 1}],
        }
        path = tmp_path / "none_src.ipynb"
        with open(path, "w") as f:
            json.dump(nb, f)
        issues = validate_notebook(path)
        assert len(issues) >= 1

    def test_error_output_reported(self, tmp_path):
        path = tmp_path / "err.ipynb"
        error_out = {
            "output_type": "error",
            "ename": "ValueError",
            "evalue": "oops",
            "traceback": [],
        }
        _write_notebook(path, [_code_cell("raise ValueError()", [error_out])])
        issues = validate_notebook(path)
        assert any("error output" in i.lower() for i in issues)

    def test_multiple_issues(self, tmp_path):
        path = tmp_path / "multi.ipynb"
        error_out = {"output_type": "error", "ename": "E", "evalue": "v", "traceback": []}
        _write_notebook(path, [_code_cell(""), _code_cell("raise E", [error_out])])
        issues = validate_notebook(path)
        assert len(issues) >= 2

    def test_markdown_cell_empty_also_flagged(self, tmp_path):
        path = tmp_path / "md_empty.ipynb"
        _write_notebook(path, [_markdown_cell("")])
        issues = validate_notebook(path)
        assert len(issues) >= 1

    def test_non_error_output_not_reported(self, tmp_path):
        path = tmp_path / "stream.ipynb"
        stream_out = {"output_type": "stream", "name": "stdout", "text": "hello"}
        _write_notebook(path, [_code_cell("print('hello')", [stream_out])])
        issues = validate_notebook(path)
        # Only issue might be empty cell check - no error output issue
        assert not any("error output" in i.lower() for i in issues)


# ---------------------------------------------------------------------------
# is_sorted()
# ---------------------------------------------------------------------------


class TestIsSorted:
    def test_empty_dict(self):
        assert is_sorted({}) is True

    def test_single_entry(self):
        assert is_sorted({"alice": {}}) is True

    def test_sorted_dict(self):
        assert is_sorted({"alice": {}, "bob": {}, "charlie": {}}) is True

    def test_unsorted_dict(self):
        assert is_sorted({"charlie": {}, "alice": {}, "bob": {}}) is False

    def test_case_insensitive_sorted(self):
        # 'Alice' < 'bob' case-insensitively
        assert is_sorted({"Alice": {}, "bob": {}, "Charlie": {}}) is True

    def test_case_insensitive_unsorted(self):
        assert is_sorted({"Bob": {}, "Alice": {}}) is False

    def test_mixed_case_order(self):
        # "anthropic" < "Bob" case-insensitively
        assert is_sorted({"anthropic": {}, "Bob": {}}) is True


# ---------------------------------------------------------------------------
# sort_authors()
# ---------------------------------------------------------------------------


class TestSortAuthors:
    def test_check_only_already_sorted(self):
        data = {"alice": {"name": "Alice"}, "bob": {"name": "Bob"}}
        changed = sort_authors(data, check_only=True)
        assert changed is False

    def test_check_only_unsorted(self):
        data = {"charlie": {"name": "Charlie"}, "alice": {"name": "Alice"}}
        changed = sort_authors(data, check_only=True)
        assert changed is True

    def test_check_only_does_not_write(self, tmp_path, monkeypatch):
        """check_only=True must not write anything."""
        fake_file = tmp_path / "authors.yaml"
        monkeypatch.setattr(_validate_authors_mod, "AUTHORS_FILE", fake_file)
        data = {"z": {}, "a": {}}
        sort_authors(data, check_only=True)
        assert not fake_file.exists()

    def test_fix_writes_sorted_file(self, tmp_path, monkeypatch):
        fake_file = tmp_path / "authors.yaml"
        monkeypatch.setattr(_validate_authors_mod, "AUTHORS_FILE", fake_file)
        data = {"charlie": {"name": "Charlie"}, "alice": {"name": "Alice"}}
        sort_authors(data, check_only=False)
        assert fake_file.exists()
        content = fake_file.read_text(encoding="utf-8")
        # alice should appear before charlie in sorted output
        assert content.index("alice") < content.index("charlie")

    def test_fix_returns_true(self, tmp_path, monkeypatch):
        fake_file = tmp_path / "authors.yaml"
        monkeypatch.setattr(_validate_authors_mod, "AUTHORS_FILE", fake_file)
        data = {"b": {}, "a": {}}
        result = sort_authors(data, check_only=False)
        assert result is True

    def test_case_insensitive_sort(self, tmp_path, monkeypatch):
        fake_file = tmp_path / "authors.yaml"
        monkeypatch.setattr(_validate_authors_mod, "AUTHORS_FILE", fake_file)
        data = {"Bob": {}, "alice": {}, "Charlie": {}}
        sort_authors(data, check_only=False)
        content = fake_file.read_text(encoding="utf-8")
        # alice < Bob < Charlie (case-insensitive)
        assert content.index("alice") < content.index("Bob")
        assert content.index("Bob") < content.index("Charlie")


# ---------------------------------------------------------------------------
# show_diff()
# ---------------------------------------------------------------------------


class TestShowDiff:
    def test_prints_current_and_expected(self, capsys):
        keys = ["charlie", "alice", "bob"]
        sorted_keys = ["alice", "bob", "charlie"]
        show_diff(keys, sorted_keys)
        captured = capsys.readouterr()
        assert "Current order" in captured.out
        assert "Expected order" in captured.out
        assert "charlie" in captured.out
        assert "alice" in captured.out

    def test_shows_out_of_place(self, capsys):
        keys = ["b", "a"]
        sorted_keys = ["a", "b"]
        show_diff(keys, sorted_keys)
        captured = capsys.readouterr()
        assert "Out of place" in captured.out

    def test_identical_lists_no_out_of_place_entries(self, capsys):
        keys = ["a", "b", "c"]
        sorted_keys = ["a", "b", "c"]
        show_diff(keys, sorted_keys)
        captured = capsys.readouterr()
        # No position mismatches
        assert "Position" not in captured.out
