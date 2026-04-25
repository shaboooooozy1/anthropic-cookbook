"""Unit tests for scripts/validate_all_notebooks.py.

The NotebookValidator class drives the comprehensive validation pipeline used
by maintainers and the dashboard. We exercise validate_notebook() directly
against synthetic notebook fixtures to lock in the issue-detection contract:
empty cells, error outputs, deprecated/dated model IDs, and hardcoded keys.
We never run the full execution path (mode='full' + ANTHROPIC_API_KEY); these
are mode='quick' tests so they're hermetic.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "validate_all_notebooks.py"


def _load_validator_module():
    """Import scripts/validate_all_notebooks.py as a module.

    The scripts/ directory is not a package, so we load it via importlib
    rather than relying on sys.path manipulation that could leak across tests.
    """
    spec = importlib.util.spec_from_file_location("validate_all_notebooks", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["validate_all_notebooks"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def validator_module():
    return _load_validator_module()


@pytest.fixture
def validator(validator_module, tmp_path, monkeypatch):
    """Fresh NotebookValidator with state files isolated to tmp_path."""
    monkeypatch.chdir(tmp_path)
    return validator_module.NotebookValidator()


def _write_notebook(path: Path, cells: list[dict]) -> Path:
    notebook = {
        "cells": cells,
        "metadata": {
            "kernelspec": {"name": "python3", "display_name": "Python 3", "language": "python"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    path.write_text(json.dumps(notebook), encoding="utf-8")
    return path


def _code(source: str, *, execution_count=1, outputs=None) -> dict:
    return {
        "cell_type": "code",
        "execution_count": execution_count,
        "source": source,
        "outputs": outputs or [],
        "metadata": {},
    }


class TestStructuralChecks:
    def test_clean_notebook_passes(self, validator, tmp_path):
        nb = _write_notebook(tmp_path / "clean.ipynb", [_code("print('hi')")])
        result = validator.validate_notebook(nb, mode="quick")
        assert result["status"] == "pass"
        assert result["issues"] == []

    def test_invalid_json_is_critical(self, validator, tmp_path):
        bad = tmp_path / "bad.ipynb"
        bad.write_text("{not json", encoding="utf-8")
        result = validator.validate_notebook(bad, mode="quick")
        assert result["status"] == "error"
        assert result["issues"][0]["type"] == "invalid_json"
        assert result["issues"][0]["severity"] == "critical"

    def test_empty_cell_reported_as_info(self, validator, tmp_path):
        nb = _write_notebook(
            tmp_path / "empty.ipynb",
            [_code(""), _code("print('hi')")],
        )
        result = validator.validate_notebook(nb, mode="quick")
        types = [i["type"] for i in result["issues"]]
        assert "empty_cell" in types
        # Empty cells alone shouldn't fail the notebook.
        assert result["status"] == "pass"


class TestErrorOutputs:
    def test_error_output_demotes_to_warning(self, validator, tmp_path):
        nb = _write_notebook(
            tmp_path / "err.ipynb",
            [
                _code(
                    "raise RuntimeError('boom')",
                    outputs=[{"output_type": "error", "ename": "RuntimeError", "evalue": "boom"}],
                )
            ],
        )
        result = validator.validate_notebook(nb, mode="quick")
        assert result["status"] == "warning"
        assert any(i["type"] == "error_output" for i in result["issues"])


class TestDeprecatedModels:
    """Lock in the deprecated → current model mapping.

    These IDs are the ones the validator promises to flag. If a future Claude
    release adds a new deprecation, that entry should be added here too.
    """

    @pytest.mark.parametrize(
        "old_id,new_id",
        [
            ("claude-3-5-sonnet-20240620", "claude-sonnet-4-6"),
            ("claude-3-5-sonnet-20241022", "claude-sonnet-4-6"),
            ("claude-3-5-sonnet-latest", "claude-sonnet-4-6"),
            ("claude-3-haiku-20240307", "claude-haiku-4-5"),
            ("claude-3-5-haiku-20241022", "claude-haiku-4-5"),
            ("claude-3-opus-20240229", "claude-opus-4-6"),
            ("claude-3-opus-latest", "claude-opus-4-6"),
            ("claude-sonnet-4-20250514", "claude-sonnet-4-6"),
            ("claude-opus-4-20250514", "claude-opus-4-6"),
            ("claude-opus-4-1", "claude-opus-4-6"),
            ("claude-sonnet-4-5-20250929", "claude-sonnet-4-6"),
            ("claude-sonnet-4-5", "claude-sonnet-4-6"),
            ("claude-opus-4-5-20251101", "claude-opus-4-6"),
            ("claude-opus-4-5", "claude-opus-4-6"),
        ],
    )
    def test_deprecated_model_flagged(self, validator, tmp_path, old_id, new_id):
        nb = _write_notebook(
            tmp_path / "model.ipynb",
            [_code(f'client.messages.create(model="{old_id}", ...)')],
        )
        result = validator.validate_notebook(nb, mode="quick")
        deprecated = [i for i in result["issues"] if i["type"] == "deprecated_model"]
        assert deprecated, f"{old_id} should have been flagged"
        assert deprecated[0]["details"]["current"] == old_id
        assert deprecated[0]["details"]["suggested"] == new_id

    def test_current_model_not_flagged(self, validator, tmp_path):
        nb = _write_notebook(
            tmp_path / "current.ipynb",
            [_code('model = "claude-sonnet-4-6"')],
        )
        result = validator.validate_notebook(nb, mode="quick")
        assert not any(i["type"] == "deprecated_model" for i in result["issues"])

    def test_dated_api_id_flagged(self, validator, tmp_path):
        # 3-segment dated API IDs are caught by the dated_pattern regex.
        nb = _write_notebook(
            tmp_path / "dated.ipynb",
            [_code('model = "claude-haiku-4-20250514"')],
        )
        result = validator.validate_notebook(nb, mode="quick")
        assert any(i["type"] == "dated_model_id" for i in result["issues"])

    @pytest.mark.xfail(
        reason=(
            "Known gap: the dated_pattern regex r'(?<!anthropic\\.)claude-\\w+-[\\d.]+-\\d{8}' "
            "only matches single-word model names (e.g. claude-haiku-4-20250101). "
            "It misses 4-segment IDs like claude-sonnet-4-5-20250929 because \\w+ "
            "doesn't span the hyphen. Today these are caught by the deprecated_models "
            "exact-match list, but new dated IDs would slip through."
        ),
        strict=True,
    )
    def test_four_segment_dated_id_flagged(self, validator, tmp_path):
        # Synthetic ID not in the deprecated_models dict, to isolate the regex.
        nb = _write_notebook(
            tmp_path / "dated4.ipynb",
            [_code('model = "claude-future-9-9-20260101"')],
        )
        result = validator.validate_notebook(nb, mode="quick")
        assert any(i["type"] == "dated_model_id" for i in result["issues"])

    def test_bedrock_dated_id_not_flagged_as_dated(self, validator, tmp_path):
        # Bedrock IDs require a date — the regex uses a lookbehind to skip them.
        nb = _write_notebook(
            tmp_path / "bedrock.ipynb",
            [_code('model = "anthropic.claude-sonnet-4-5-20250929-v1:0"')],
        )
        result = validator.validate_notebook(nb, mode="quick")
        dated_issues = [i for i in result["issues"] if i["type"] == "dated_model_id"]
        assert dated_issues == []


class TestApiKeyChecks:
    def test_hardcoded_key_is_critical(self, validator, tmp_path):
        nb = _write_notebook(
            tmp_path / "leaked.ipynb",
            [_code('API_KEY = "sk-ant-api03-LEAKED-xxxxxx"')],
        )
        result = validator.validate_notebook(nb, mode="quick")
        assert result["status"] == "error"
        leak = [i for i in result["issues"] if i["type"] == "hardcoded_api_key"]
        assert leak and leak[0]["severity"] == "critical"

    def test_api_key_assignment_without_env_flagged(self, validator, tmp_path):
        # api_key= present, but no os.environ / getenv reference.
        nb = _write_notebook(
            tmp_path / "noenv.ipynb",
            [_code("client = Anthropic(api_key=user_supplied_value)")],
        )
        result = validator.validate_notebook(nb, mode="quick")
        assert any(i["type"] == "api_key_not_env" for i in result["issues"])

    def test_api_key_from_environ_passes(self, validator, tmp_path):
        nb = _write_notebook(
            tmp_path / "ok.ipynb",
            [_code('import os\nclient = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))')],
        )
        result = validator.validate_notebook(nb, mode="quick")
        api_issues = [
            i for i in result["issues"] if i["type"] in {"hardcoded_api_key", "api_key_not_env"}
        ]
        assert api_issues == []

    def test_api_key_from_getenv_passes(self, validator, tmp_path):
        nb = _write_notebook(
            tmp_path / "ok2.ipynb",
            [_code('client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))')],
        )
        result = validator.validate_notebook(nb, mode="quick")
        assert not any(i["type"] == "api_key_not_env" for i in result["issues"])


class TestQuickModeDoesNotExecute:
    def test_quick_mode_skips_execution_even_with_api_key(self, validator, tmp_path, monkeypatch):
        """mode='quick' must never call execute_notebook(), even if a key is set.

        Notebook execution is slow and network-dependent; CI runs structural
        checks in 'quick' mode and trusts that path to be hermetic.
        """
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-not-real")
        called = []
        monkeypatch.setattr(
            validator,
            "execute_notebook",
            lambda *a, **kw: called.append(a) or {"success": True},
        )
        nb = _write_notebook(tmp_path / "x.ipynb", [_code("print('hi')")])
        validator.validate_notebook(nb, mode="quick")
        assert called == []
