from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import validate_notebooks


def _write_notebook(path: Path, cells: list[dict]) -> None:
    path.write_text(json.dumps({"cells": cells}), encoding="utf-8")


def test_validate_notebook_reports_empty_cells_and_error_outputs(tmp_path: Path):
    nb_path = tmp_path / "nb.ipynb"
    _write_notebook(
        nb_path,
        cells=[
            {"cell_type": "markdown", "source": []},
            {"cell_type": "code", "source": ["1"], "outputs": [{"output_type": "error"}]},
        ],
    )

    issues = validate_notebooks.validate_notebook(nb_path)
    assert any("Empty cell" in issue for issue in issues)
    assert any("Contains error output" in issue for issue in issues)


def test_main_exits_zero_when_no_notebooks(capsys: pytest.CaptureFixture[str], monkeypatch):
    monkeypatch.setattr(validate_notebooks.sys, "argv", ["validate_notebooks.py"])
    with pytest.raises(SystemExit) as exc:
        validate_notebooks.main()
    assert exc.value.code == 0
    assert "No notebooks to validate" in capsys.readouterr().out


def test_main_exits_one_when_issues_found(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch
):
    nb_path = tmp_path / "bad.ipynb"
    _write_notebook(nb_path, cells=[{"cell_type": "code", "source": [], "outputs": []}])

    monkeypatch.setattr(validate_notebooks.sys, "argv", ["validate_notebooks.py", str(nb_path)])
    with pytest.raises(SystemExit) as exc:
        validate_notebooks.main()
    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "Found issues" in out
    assert str(nb_path) in out


def test_main_exits_zero_when_no_issues(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch
):
    nb_path = tmp_path / "ok.ipynb"
    _write_notebook(nb_path, cells=[{"cell_type": "markdown", "source": ["# ok"]}])

    monkeypatch.setattr(validate_notebooks.sys, "argv", ["validate_notebooks.py", str(nb_path)])
    with pytest.raises(SystemExit) as exc:
        validate_notebooks.main()
    assert exc.value.code == 0
    assert "validated successfully" in capsys.readouterr().out
