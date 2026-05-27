from __future__ import annotations

import json
import subprocess
from datetime import datetime
from pathlib import Path

import pytest

from scripts.validate_all_notebooks import NotebookValidator


def _write_notebook(path: Path, cells: list[dict]) -> None:
    path.write_text(json.dumps({"cells": cells}), encoding="utf-8")


def test_load_state_defaults_when_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    validator = NotebookValidator()
    assert validator.state["version"] == "1.0"
    assert validator.state["notebooks"] == {}


def test_load_state_warns_on_invalid_json(
    tmp_path: Path, monkeypatch, capsys: pytest.CaptureFixture[str]
):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".notebook_validation_state.json").write_text("{bad json", encoding="utf-8")
    validator = NotebookValidator()
    assert validator.state["notebooks"] == {}
    assert "starting fresh" in capsys.readouterr().out.lower()


def test_save_state_updates_history(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    validator = NotebookValidator()
    validator.state["notebooks"] = {
        "a.ipynb": {"status": "pass"},
        "b.ipynb": {"status": "warning"},
    }

    validator.save_state()
    saved = json.loads((tmp_path / ".notebook_validation_state.json").read_text(encoding="utf-8"))
    assert saved["history"]
    assert saved["history"][-1]["date"] == datetime.now().strftime("%Y-%m-%d")


def test_validate_notebook_reports_expected_issues(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    validator = NotebookValidator()

    nb_path = tmp_path / "nb.ipynb"
    _write_notebook(
        nb_path,
        cells=[
            {"cell_type": "markdown", "source": []},
            {
                "cell_type": "code",
                "source": [
                    "model = 'claude-sonnet-4-5-20250929'\\n",
                    "old = 'claude-3-5-sonnet-latest'\\n",
                ],
                "outputs": [{"output_type": "error"}],
            },
        ],
    )

    result = validator.validate_notebook(nb_path, mode="quick")
    issue_types = {i["type"] for i in result["issues"]}
    assert "empty_cell" in issue_types
    assert "error_output" in issue_types
    assert "dated_model_id" in issue_types
    assert "deprecated_model" in issue_types
    assert result["status"] == "warning"


def test_validate_notebook_hardcoded_key_is_critical(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(tmp_path)
    validator = NotebookValidator()

    nb_path = tmp_path / "nb.ipynb"
    _write_notebook(
        nb_path,
        cells=[{"cell_type": "code", "source": ["sk-ant-123\\n"], "outputs": []}],
    )

    result = validator.validate_notebook(nb_path, mode="quick")
    assert result["status"] == "error"
    assert any(i["type"] == "hardcoded_api_key" for i in result["issues"])


def test_validate_notebook_api_key_not_env_is_critical(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(tmp_path)
    validator = NotebookValidator()

    nb_path = tmp_path / "nb.ipynb"
    _write_notebook(
        nb_path,
        cells=[{"cell_type": "code", "source": ["Anthropic(api_key='literal')\\n"], "outputs": []}],
    )

    result = validator.validate_notebook(nb_path, mode="quick")
    assert result["status"] == "error"
    assert any(i["type"] == "api_key_not_env" for i in result["issues"])


def test_full_mode_executes_when_api_key_set(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    validator = NotebookValidator()

    nb_path = tmp_path / "nb.ipynb"
    _write_notebook(
        nb_path, cells=[{"cell_type": "code", "source": ["print(1)\\n"], "outputs": []}]
    )

    monkeypatch.setenv("ANTHROPIC_API_KEY", "dummy")
    monkeypatch.setattr(
        validator, "execute_notebook", lambda _p: {"success": False, "error": "nope"}
    )

    result = validator.validate_notebook(nb_path, mode="full")
    assert result["status"] == "error"
    assert any(i["type"] == "execution_failure" for i in result["issues"])


def test_execute_notebook_handles_timeouts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    validator = NotebookValidator()

    nb_path = tmp_path / "nb.ipynb"
    _write_notebook(nb_path, cells=[])

    def fake_run(*_args, **_kwargs):  # noqa: ANN001
        raise subprocess.TimeoutExpired(cmd=["jupyter"], timeout=1)

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert validator.execute_notebook(nb_path)["success"] is False


def test_generate_dashboard_handles_empty_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    validator = NotebookValidator()
    assert "No notebooks validated yet" in validator.generate_dashboard()


def test_validation_does_not_execute_without_api_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(tmp_path)
    validator = NotebookValidator()
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    nb_path = tmp_path / "nb.ipynb"
    _write_notebook(
        nb_path, cells=[{"cell_type": "code", "source": ["print(1)\\n"], "outputs": []}]
    )

    def explode(_path):  # noqa: ANN001
        raise AssertionError("execute_notebook should not be called")

    monkeypatch.setattr(validator, "execute_notebook", explode)
    result = validator.validate_notebook(nb_path, mode="full")
    assert result["status"] == "pass"


def test_generate_dashboard_includes_trend_and_quick_actions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(tmp_path)
    validator = NotebookValidator()
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    validator.state["history"] = [
        {"date": "2000-01-01", "passing": 1, "total": 2},
        {"date": "2000-01-02", "passing": 2, "total": 2},
    ]
    validator.state["notebooks"] = {
        "a.ipynb": {
            "status": "error",
            "issues": [{"type": "hardcoded_api_key", "severity": "critical", "details": "x"}],
        },
        "b.ipynb": {
            "status": "warning",
            "issues": [{"type": "deprecated_model", "severity": "warning", "details": "y"}],
        },
    }

    dashboard = validator.generate_dashboard()
    assert "Notebook Validation Dashboard" in dashboard
    assert "Critical Issues" in dashboard
    assert "Quick Actions" in dashboard
    assert "Set ANTHROPIC_API_KEY" in dashboard


def test_export_github_issue_contains_quick_fix_commands(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(tmp_path)
    validator = NotebookValidator()
    validator.state["notebooks"] = {
        "a.ipynb": {
            "status": "error",
            "issues": [{"type": "hardcoded_api_key", "severity": "critical", "details": "x"}],
        }
    }

    issue = validator.export_github_issue()
    assert "Notebook Validation Report" in issue
    assert "Quick Fix Commands" in issue


def test_fix_deprecated_models_rewrites_notebook(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    validator = NotebookValidator()
    nb_path = tmp_path / "nb.ipynb"
    _write_notebook(
        nb_path,
        cells=[
            {
                "cell_type": "code",
                "source": ["model = 'claude-3-5-sonnet-20240620'\\n"],
                "outputs": [],
            }
        ],
    )

    assert validator.fix_deprecated_models(nb_path) is True
    assert "claude-sonnet-4-6" in nb_path.read_text(encoding="utf-8")
