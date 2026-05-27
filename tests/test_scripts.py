"""Unit tests for CLI scripts under ``scripts/``.

These focus on pure logic / argument parsing without executing external tools.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"


def load_script_module(module_name: str, script_filename: str):
    script_path = SCRIPTS_DIR / script_filename
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestValidateNotebooksScript:
    def test_validate_notebook_finds_empty_cells_and_error_outputs(self, tmp_path: Path):
        validate_notebooks = load_script_module("validate_notebooks_test", "validate_notebooks.py")

        nb = {
            "cells": [
                {"cell_type": "markdown", "source": []},
                {
                    "cell_type": "code",
                    "source": ["1/0"],
                    "outputs": [
                        {"output_type": "error", "ename": "ZeroDivisionError", "evalue": "x"}
                    ],
                },
            ]
        }
        nb_path = tmp_path / "nb.ipynb"
        nb_path.write_text(json.dumps(nb), encoding="utf-8")

        issues = validate_notebooks.validate_notebook(nb_path)
        assert any("Empty cell found" in i for i in issues)
        assert any("Contains error output" in i for i in issues)

    def test_main_exits_zero_when_no_notebooks(self, monkeypatch):
        validate_notebooks = load_script_module("validate_notebooks_test2", "validate_notebooks.py")
        monkeypatch.setattr(sys, "argv", ["validate_notebooks.py"])
        with pytest.raises(SystemExit) as exc:
            validate_notebooks.main()
        assert exc.value.code == 0

    def test_main_exits_nonzero_when_issues_found(self, tmp_path: Path, monkeypatch):
        validate_notebooks = load_script_module("validate_notebooks_test3", "validate_notebooks.py")

        nb = {"cells": [{"cell_type": "markdown", "source": []}]}
        nb_path = tmp_path / "bad.ipynb"
        nb_path.write_text(json.dumps(nb), encoding="utf-8")

        monkeypatch.setattr(sys, "argv", ["validate_notebooks.py", str(nb_path)])
        with pytest.raises(SystemExit) as exc:
            validate_notebooks.main()
        assert exc.value.code == 1


class TestValidateAuthorsSortedScript:
    def test_sort_authors_check_only_detects_changes(self, tmp_path: Path):
        validate_authors = load_script_module("validate_authors_test", "validate_authors_sorted.py")
        validate_authors.AUTHORS_FILE = tmp_path / "authors.yaml"
        assert validate_authors.sort_authors({"b": 2, "a": 1}, check_only=True) is True

    def test_sort_authors_writes_header_and_sorts(self, tmp_path: Path):
        validate_authors = load_script_module(
            "validate_authors_test2", "validate_authors_sorted.py"
        )
        validate_authors.AUTHORS_FILE = tmp_path / "authors.yaml"

        changed = validate_authors.sort_authors({"b": 2, "a": 1}, check_only=False)
        assert changed is True

        content = validate_authors.AUTHORS_FILE.read_text(encoding="utf-8")
        assert content.startswith(validate_authors.HEADER)
        assert content.index("\na:") < content.index("\nb:")

    def test_main_validation_mode_exits_nonzero_when_unsorted(self, tmp_path: Path, monkeypatch):
        validate_authors = load_script_module(
            "validate_authors_test3", "validate_authors_sorted.py"
        )
        validate_authors.AUTHORS_FILE = tmp_path / "authors.yaml"

        validate_authors.AUTHORS_FILE.write_text("b: {}\na: {}\n", encoding="utf-8")

        monkeypatch.setattr(sys, "argv", ["validate_authors_sorted.py"])
        with pytest.raises(SystemExit) as exc:
            validate_authors.main()
        assert exc.value.code == 1


class TestTestNotebooksScript:
    def test_main_quick_requires_target(self, monkeypatch):
        test_notebooks = load_script_module("test_notebooks_test", "test_notebooks.py")
        monkeypatch.setattr(sys, "argv", ["test_notebooks.py", "--quick"])
        assert test_notebooks.main() == 1

    def test_main_routes_to_tox_env_selection(self, monkeypatch):
        test_notebooks = load_script_module("test_notebooks_test2", "test_notebooks.py")

        calls: list[tuple[str, list[str]]] = []

        def fake_run_tox(env: str, extra_args: list[str]) -> int:
            calls.append((env, extra_args))
            return 7

        monkeypatch.setattr(test_notebooks, "run_tox", fake_run_tox)
        monkeypatch.setattr(
            sys, "argv", ["test_notebooks.py", "--tox", "--execute", "--notebook", "x.ipynb"]
        )

        assert test_notebooks.main() == 7
        assert calls[0][0] == "execution-single"

    def test_list_notebooks_uses_helpers(self, monkeypatch, capsys):
        test_notebooks = load_script_module("test_notebooks_test3", "test_notebooks.py")

        sample_nb = test_notebooks.PROJECT_ROOT / "tool_use" / "calculator_tool.ipynb"

        monkeypatch.setattr(test_notebooks, "find_all_notebooks", lambda _root: [sample_nb])
        monkeypatch.setattr(
            test_notebooks,
            "validate_notebook_structure",
            lambda _path: SimpleNamespace(
                cells=[SimpleNamespace(cell_type="code")], errors=[], warnings=[]
            ),
        )

        test_notebooks.list_notebooks()
        out = capsys.readouterr().out
        assert "Total:" in out

    def test_run_pytest_builds_expected_command(self, monkeypatch):
        test_notebooks = load_script_module("test_notebooks_test4", "test_notebooks.py")

        captured = {}

        def fake_call(cmd, cwd):
            captured["cmd"] = cmd
            captured["cwd"] = cwd
            return 0

        monkeypatch.setattr(test_notebooks.subprocess, "call", fake_call)
        assert test_notebooks.run_pytest(["--notebook", "x.ipynb"]) == 0
        assert captured["cmd"][:3] == [sys.executable, "-m", "pytest"]
        assert captured["cwd"] == test_notebooks.PROJECT_ROOT

    def test_run_tox_builds_expected_command(self, monkeypatch):
        test_notebooks = load_script_module("test_notebooks_test5", "test_notebooks.py")

        captured = {}

        def fake_call(cmd, cwd):
            captured["cmd"] = cmd
            captured["cwd"] = cwd
            return 0

        monkeypatch.setattr(test_notebooks.subprocess, "call", fake_call)
        assert test_notebooks.run_tox("structure", ["--", "-k", "x"]) == 0
        assert captured["cmd"][:3] == ["tox", "-e", "structure"]
        assert captured["cwd"] == test_notebooks.PROJECT_ROOT


class TestValidateAllNotebooksScript:
    def test_load_state_defaults_when_missing(self, tmp_path: Path, monkeypatch):
        validate_all = load_script_module(
            "validate_all_notebooks_test", "validate_all_notebooks.py"
        )
        monkeypatch.chdir(tmp_path)

        v = validate_all.NotebookValidator()
        assert v.state["version"] == "1.0"
        assert v.state["notebooks"] == {}

    def test_load_state_recovers_from_invalid_json(self, tmp_path: Path, monkeypatch, capsys):
        validate_all = load_script_module(
            "validate_all_notebooks_test2", "validate_all_notebooks.py"
        )
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".notebook_validation_state.json").write_text("{not json", encoding="utf-8")

        v = validate_all.NotebookValidator()
        assert v.state["notebooks"] == {}
        out = capsys.readouterr().out
        assert "starting fresh" in out

    def test_validate_notebook_invalid_json(self, tmp_path: Path, monkeypatch):
        validate_all = load_script_module(
            "validate_all_notebooks_test3", "validate_all_notebooks.py"
        )
        monkeypatch.chdir(tmp_path)
        nb = tmp_path / "bad.ipynb"
        nb.write_text("{not json", encoding="utf-8")

        v = validate_all.NotebookValidator()
        result = v.validate_notebook(nb, mode="quick")
        assert result["status"] == "error"
        assert result["issues"][0]["type"] == "invalid_json"

    def test_validate_notebook_flags_api_key_not_env(self, tmp_path: Path, monkeypatch):
        validate_all = load_script_module(
            "validate_all_notebooks_test4", "validate_all_notebooks.py"
        )
        monkeypatch.chdir(tmp_path)

        nb = {
            "cells": [
                {
                    "cell_type": "code",
                    "source": ["client = Anthropic(api_key='literal')"],
                    "outputs": [],
                }
            ]
        }
        nb_path = tmp_path / "nb.ipynb"
        nb_path.write_text(json.dumps(nb), encoding="utf-8")

        v = validate_all.NotebookValidator()
        result = v.validate_notebook(nb_path, mode="quick")
        assert result["status"] == "error"
        assert any(i["type"] == "api_key_not_env" for i in result["issues"])

    def test_generate_dashboard_summarizes_state(self, tmp_path: Path, monkeypatch):
        validate_all = load_script_module(
            "validate_all_notebooks_test5", "validate_all_notebooks.py"
        )
        monkeypatch.chdir(tmp_path)

        v = validate_all.NotebookValidator()
        v.state["notebooks"] = {
            "a.ipynb": {"status": "pass", "issues": []},
            "b.ipynb": {
                "status": "warning",
                "issues": [{"type": "deprecated_model", "severity": "warning"}],
            },
        }
        v.state["history"] = [{"date": "2026-01-01", "passing": 1, "total": 2}]

        dash = v.generate_dashboard()
        assert "Notebook Validation Dashboard" in dash
        assert "Warnings" in dash

    def test_save_state_writes_history(self, tmp_path: Path, monkeypatch):
        validate_all = load_script_module(
            "validate_all_notebooks_test6", "validate_all_notebooks.py"
        )
        monkeypatch.chdir(tmp_path)

        v = validate_all.NotebookValidator()
        v.state["notebooks"] = {
            "a.ipynb": {"status": "pass"},
            "b.ipynb": {"status": "error"},
        }
        v.save_state()

        saved = json.loads(
            (tmp_path / ".notebook_validation_state.json").read_text(encoding="utf-8")
        )
        assert "history" in saved
        assert saved["history"]

    def test_execute_notebook_error_message_trimmed(self, tmp_path: Path, monkeypatch):
        validate_all = load_script_module(
            "validate_all_notebooks_test7", "validate_all_notebooks.py"
        )
        monkeypatch.chdir(tmp_path)

        v = validate_all.NotebookValidator()

        class Result:
            returncode = 1
            stderr = "x" * 500 + "\nError: something bad\n" + "y" * 500

        monkeypatch.setattr(
            validate_all.subprocess,
            "run",
            lambda *_args, **_kwargs: Result(),
        )

        res = v.execute_notebook(tmp_path / "nb.ipynb")
        assert res["success"] is False
        assert len(res["error"]) <= 200

    def test_export_github_issue_contains_fix_commands(self, tmp_path: Path, monkeypatch):
        validate_all = load_script_module(
            "validate_all_notebooks_test8", "validate_all_notebooks.py"
        )
        monkeypatch.chdir(tmp_path)

        v = validate_all.NotebookValidator()
        v.state["notebooks"] = {
            "a.ipynb": {
                "status": "warning",
                "issues": [{"type": "deprecated_model", "severity": "warning"}],
            },
            "b.ipynb": {
                "status": "error",
                "issues": [{"type": "hardcoded_api_key", "severity": "critical", "details": "x"}],
            },
        }
        v.state["history"] = [{"date": "2026-01-01", "passing": 0, "total": 2}]

        md = v.export_github_issue()
        assert "Quick Fix Commands" in md
        assert "validate_all_notebooks.py --auto-fix" in md
