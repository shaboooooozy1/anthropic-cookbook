from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import test_notebooks


def test_run_pytest_builds_command(monkeypatch: pytest.MonkeyPatch):
    captured = {}

    def fake_call(cmd, cwd):  # noqa: ANN001
        captured["cmd"] = cmd
        captured["cwd"] = cwd
        return 0

    monkeypatch.setattr(test_notebooks.subprocess, "call", fake_call)
    assert test_notebooks.run_pytest(["--notebook", "x.ipynb"]) == 0
    cmd = captured["cmd"]
    assert cmd[:3] == [test_notebooks.sys.executable, "-m", "pytest"]
    assert "tests/notebook_tests/test_notebooks.py" in cmd
    assert captured["cwd"] == test_notebooks.PROJECT_ROOT


def test_run_tox_builds_command(monkeypatch: pytest.MonkeyPatch):
    captured = {}

    def fake_call(cmd, cwd):  # noqa: ANN001
        captured["cmd"] = cmd
        captured["cwd"] = cwd
        return 0

    monkeypatch.setattr(test_notebooks.subprocess, "call", fake_call)
    assert test_notebooks.run_tox("structure", ["--", "-k", "x"]) == 0
    assert captured["cmd"][:3] == ["tox", "-e", "structure"]
    assert captured["cwd"] == test_notebooks.PROJECT_ROOT


def test_main_quick_requires_notebook_or_dir(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(test_notebooks.sys, "argv", ["test_notebooks.py", "--quick"])
    assert test_notebooks.main() == 1


def test_main_quick_single_notebook(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(test_notebooks, "run_quick_validation", lambda _p: True)
    monkeypatch.setattr(
        test_notebooks.sys,
        "argv",
        ["test_notebooks.py", "--quick", "--notebook", "tool_use/calculator_tool.ipynb"],
    )
    assert test_notebooks.main() == 0


def test_list_notebooks_handles_validation_errors(monkeypatch: pytest.MonkeyPatch):
    notebooks = [test_notebooks.PROJECT_ROOT / "a.ipynb", test_notebooks.PROJECT_ROOT / "b.ipynb"]

    def fake_find_all_notebooks(_root):  # noqa: ANN001
        return notebooks

    def fake_validate(nb_path):  # noqa: ANN001
        if nb_path.name == "b.ipynb":
            raise RuntimeError("bad")
        return SimpleNamespace(
            cells=[SimpleNamespace(cell_type="markdown"), SimpleNamespace(cell_type="code")]
        )

    monkeypatch.setattr(test_notebooks, "find_all_notebooks", fake_find_all_notebooks)
    monkeypatch.setattr(test_notebooks, "validate_notebook_structure", fake_validate)
    monkeypatch.setattr(test_notebooks.console, "print", lambda *_a, **_k: None)

    test_notebooks.list_notebooks()


def test_main_tox_selects_single_env(monkeypatch: pytest.MonkeyPatch):
    captured = {}

    def fake_run_tox(env, extra):  # noqa: ANN001
        captured["env"] = env
        captured["extra"] = extra
        return 0

    monkeypatch.setattr(test_notebooks, "run_tox", fake_run_tox)
    monkeypatch.setattr(
        test_notebooks.sys,
        "argv",
        ["test_notebooks.py", "--tox", "--notebook", "x.ipynb", "--", "-k", "x"],
    )
    assert test_notebooks.main() == 0
    assert captured["env"] == "structure-single"
    assert captured["extra"][0] == "--"


def test_main_tox_switches_to_execution_env(monkeypatch: pytest.MonkeyPatch):
    captured = {}

    def fake_run_tox(env, extra):  # noqa: ANN001
        captured["env"] = env
        captured["extra"] = extra
        return 0

    monkeypatch.setattr(test_notebooks, "run_tox", fake_run_tox)
    monkeypatch.setattr(
        test_notebooks.sys,
        "argv",
        ["test_notebooks.py", "--tox", "--execute", "--notebook", "x.ipynb"],
    )
    assert test_notebooks.main() == 0
    assert captured["env"] == "execution-single"
