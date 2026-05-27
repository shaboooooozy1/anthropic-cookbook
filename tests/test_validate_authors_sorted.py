from __future__ import annotations

import sys
from pathlib import Path

import yaml

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import validate_authors_sorted as vas


def write_authors(path: Path, data: dict) -> None:
    path.write_text(yaml.dump(data, sort_keys=False), encoding="utf-8")


def test_is_sorted_case_insensitive():
    assert vas.is_sorted({"alice": {}, "Bob": {}, "carol": {}})
    assert not vas.is_sorted({"Bob": {}, "alice": {}, "carol": {}})


def test_load_authors_reads_yaml(monkeypatch, tmp_path: Path):
    authors_file = tmp_path / "authors.yaml"
    write_authors(authors_file, {"alice": {"name": "Alice"}})
    monkeypatch.setattr(vas, "AUTHORS_FILE", authors_file)
    assert vas.load_authors() == {"alice": {"name": "Alice"}}


def test_sort_authors_check_only_detects_change():
    data = {"Bob": {"name": "Bob"}, "alice": {"name": "Alice"}}
    assert vas.sort_authors(data, check_only=True) is True
    assert vas.sort_authors({"alice": {}, "Bob": {}}, check_only=True) is False


def test_sort_authors_writes_sorted_yaml(monkeypatch, tmp_path: Path):
    authors_file = tmp_path / "authors.yaml"
    write_authors(authors_file, {"Bob": {"name": "Bob"}, "alice": {"name": "Alice"}})
    monkeypatch.setattr(vas, "AUTHORS_FILE", authors_file)

    changed = vas.sort_authors({"Bob": {"name": "Bob"}, "alice": {"name": "Alice"}})
    assert changed is True

    written = authors_file.read_text(encoding="utf-8")
    assert written.startswith(vas.HEADER)
    sorted_payload = yaml.safe_load(written.split("\n\n", 1)[1])
    assert list(sorted_payload.keys()) == ["alice", "Bob"]


def test_show_diff_prints_mismatches(capsys):
    vas.show_diff(["Bob", "alice"], ["alice", "Bob"])
    out = capsys.readouterr().out
    assert "Current order" in out
    assert "Expected order" in out
    assert "Position 0: got 'Bob', expected 'alice'" in out


def test_main_validation_failure(monkeypatch, tmp_path: Path, capsys):
    authors_file = tmp_path / "authors.yaml"
    write_authors(authors_file, {"Bob": {"name": "Bob"}, "alice": {"name": "Alice"}})
    monkeypatch.setattr(vas, "AUTHORS_FILE", authors_file)
    monkeypatch.setattr(sys, "argv", ["validate_authors_sorted.py"])

    try:
        vas.main()
    except SystemExit as exc:
        assert exc.code == 1
    else:
        raise AssertionError("main() did not exit")

    out = capsys.readouterr().out
    assert "not sorted alphabetically" in out
    assert "Run with --fix to sort automatically" in out


def test_main_fix_reformats_unsorted_file(monkeypatch, tmp_path: Path, capsys):
    authors_file = tmp_path / "authors.yaml"
    write_authors(authors_file, {"Bob": {"name": "Bob"}, "alice": {"name": "Alice"}})
    monkeypatch.setattr(vas, "AUTHORS_FILE", authors_file)
    monkeypatch.setattr(sys, "argv", ["validate_authors_sorted.py", "--fix"])

    try:
        vas.main()
    except SystemExit as exc:
        assert exc.code == 0
    else:
        raise AssertionError("main() did not exit")

    out = capsys.readouterr().out
    assert "1 file reformatted" in out
    data = yaml.safe_load(authors_file.read_text(encoding="utf-8").split("\n\n", 1)[1])
    assert list(data.keys()) == ["alice", "Bob"]


def test_main_sorted_file_left_unchanged(monkeypatch, tmp_path: Path, capsys):
    authors_file = tmp_path / "authors.yaml"
    write_authors(authors_file, {"alice": {"name": "Alice"}, "Bob": {"name": "Bob"}})
    monkeypatch.setattr(vas, "AUTHORS_FILE", authors_file)
    monkeypatch.setattr(sys, "argv", ["validate_authors_sorted.py"])

    try:
        vas.main()
    except SystemExit as exc:
        assert exc.code == 0
    else:
        raise AssertionError("main() did not exit")

    assert "1 file left unchanged" in capsys.readouterr().out
