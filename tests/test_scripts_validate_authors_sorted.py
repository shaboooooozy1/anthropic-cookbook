from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from scripts import validate_authors_sorted


def test_is_sorted_case_insensitive():
    assert validate_authors_sorted.is_sorted({"a": 1, "B": 2, "c": 3}) is True
    assert validate_authors_sorted.is_sorted({"b": 1, "A": 2}) is False


def test_sort_authors_check_only():
    data = {"b": 1, "A": 2}
    assert validate_authors_sorted.sort_authors(data, check_only=True) is True
    data_sorted = {"A": 2, "b": 1}
    assert validate_authors_sorted.sort_authors(data_sorted, check_only=True) is False


def test_show_diff_prints_out_of_place(capsys: pytest.CaptureFixture[str]):
    validate_authors_sorted.show_diff(["b", "A"], ["A", "b"])
    out = capsys.readouterr().out
    assert "Out of place entries" in out
    assert "got 'b', expected 'A'" in out


def test_main_validation_and_fix(tmp_path: Path, monkeypatch, capsys: pytest.CaptureFixture[str]):
    authors_path = tmp_path / "authors.yaml"
    authors_path.write_text(
        yaml.safe_dump({"b": {"name": "B"}, "A": {"name": "A"}}, sort_keys=False),
        encoding="utf-8",
    )

    monkeypatch.setattr(validate_authors_sorted, "AUTHORS_FILE", authors_path)

    # Validation mode should fail on unsorted input.
    monkeypatch.setattr(validate_authors_sorted.sys, "argv", ["validate_authors_sorted.py"])
    with pytest.raises(SystemExit) as exc:
        validate_authors_sorted.main()
    assert exc.value.code == 1
    assert "not sorted" in capsys.readouterr().out

    # Fix mode should succeed and rewrite file with header.
    monkeypatch.setattr(
        validate_authors_sorted.sys, "argv", ["validate_authors_sorted.py", "--fix"]
    )
    with pytest.raises(SystemExit) as exc:
        validate_authors_sorted.main()
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "reformatted" in out

    rewritten = authors_path.read_text(encoding="utf-8")
    assert rewritten.startswith(validate_authors_sorted.HEADER)
