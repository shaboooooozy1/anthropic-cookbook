"""Tests for ``scripts/validate_authors_sorted.py`` — the authors.yaml sort hook.

This script gates commits (pre-commit) and CI (verify-authors), so its sort and
``--fix`` behavior need to be locked down. Tests point the module at a temporary
authors file via ``monkeypatch`` so the real ``authors.yaml`` is never touched.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

# scripts/ is not a package, so add it to sys.path for import.
SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import validate_authors_sorted as vas  # noqa: E402


@pytest.fixture
def authors_file(tmp_path: Path, monkeypatch):
    """Redirect the module's AUTHORS_FILE to a temp file and return its path."""
    path = tmp_path / "authors.yaml"
    monkeypatch.setattr(vas, "AUTHORS_FILE", path)
    return path


def write_authors(path: Path, keys: list[str]) -> None:
    data = {k: {"name": k.title()} for k in keys}
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


class TestIsSorted:
    def test_sorted_keys(self):
        assert vas.is_sorted({"alice": {}, "Bob": {}, "carol": {}})

    def test_unsorted_keys(self):
        assert not vas.is_sorted({"carol": {}, "alice": {}})

    def test_case_insensitive(self):
        # Uppercase 'Bob' sorts between alice and carol case-insensitively.
        assert vas.is_sorted({"alice": {}, "Bob": {}, "carol": {}})
        assert not vas.is_sorted({"Bob": {}, "alice": {}})

    def test_single_and_empty(self):
        assert vas.is_sorted({})
        assert vas.is_sorted({"solo": {}})


class TestLoadAuthors:
    def test_round_trips_yaml(self, authors_file):
        write_authors(authors_file, ["alice", "bob"])
        data = vas.load_authors()
        assert list(data.keys()) == ["alice", "bob"]


class TestSortAuthors:
    def test_check_only_detects_unsorted(self, authors_file):
        data = {"carol": {"name": "Carol"}, "alice": {"name": "Alice"}}
        # check_only must not write the file.
        assert vas.sort_authors(data, check_only=True) is True
        assert not authors_file.exists()

    def test_check_only_passes_when_sorted(self, authors_file):
        data = {"alice": {"name": "Alice"}, "carol": {"name": "Carol"}}
        assert vas.sort_authors(data, check_only=True) is False

    def test_writes_sorted_file_with_header(self, authors_file):
        data = {"carol": {"name": "Carol"}, "alice": {"name": "Alice"}}
        vas.sort_authors(data)

        text = authors_file.read_text(encoding="utf-8")
        assert text.startswith("# yaml-language-server:")
        reloaded = yaml.safe_load(text)
        assert list(reloaded.keys()) == ["alice", "carol"]

    def test_preserves_unicode_names(self, authors_file):
        data = {"zoé": {"name": "Zoé"}, "ana": {"name": "Aná"}}
        vas.sort_authors(data)
        reloaded = yaml.safe_load(authors_file.read_text(encoding="utf-8"))
        assert reloaded["zoé"]["name"] == "Zoé"


class TestMain:
    def _run(self, monkeypatch, argv):
        monkeypatch.setattr(sys, "argv", argv)
        with pytest.raises(SystemExit) as exc:
            vas.main()
        return exc.value.code

    def test_sorted_validation_exits_zero(self, authors_file, monkeypatch, capsys):
        write_authors(authors_file, ["alice", "bob"])
        code = self._run(monkeypatch, ["validate_authors_sorted.py"])
        assert code == 0
        assert "left unchanged" in capsys.readouterr().out

    def test_unsorted_validation_exits_one(self, authors_file, monkeypatch, capsys):
        write_authors(authors_file, ["carol", "alice"])
        code = self._run(monkeypatch, ["validate_authors_sorted.py"])
        assert code == 1
        out = capsys.readouterr().out
        assert "not sorted" in out
        assert "--fix" in out

    def test_fix_rewrites_unsorted(self, authors_file, monkeypatch, capsys):
        write_authors(authors_file, ["carol", "alice"])
        code = self._run(monkeypatch, ["validate_authors_sorted.py", "--fix"])
        assert code == 0
        assert "reformatted" in capsys.readouterr().out
        reloaded = yaml.safe_load(authors_file.read_text(encoding="utf-8"))
        assert list(reloaded.keys()) == ["alice", "carol"]

    def test_fix_leaves_sorted_unchanged(self, authors_file, monkeypatch, capsys):
        write_authors(authors_file, ["alice", "bob"])
        code = self._run(monkeypatch, ["validate_authors_sorted.py", "--fix"])
        assert code == 0
        assert "left unchanged" in capsys.readouterr().out

    def test_empty_file_exits_zero(self, authors_file, monkeypatch, capsys):
        authors_file.write_text("", encoding="utf-8")
        code = self._run(monkeypatch, ["validate_authors_sorted.py"])
        assert code == 0
        assert "empty" in capsys.readouterr().out
