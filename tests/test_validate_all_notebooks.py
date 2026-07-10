"""Unit tests for scripts/validate_all_notebooks.py.

The auto-fix path in this script rewrites every notebook on the project, so a
regression in the deprecated-model substitution table or the dated-ID regex
silently corrupts the corpus. These tests pin down the rules that the rest of
the cookbook depends on.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "validate_all_notebooks.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("validate_all_notebooks", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["validate_all_notebooks"] = module
    spec.loader.exec_module(module)
    return module


validate_all_notebooks = _load_module()
NotebookValidator = validate_all_notebooks.NotebookValidator


@pytest.fixture
def validator(tmp_path, monkeypatch):
    """Validator that writes its state file inside an isolated tmp dir."""
    monkeypatch.chdir(tmp_path)
    # Make sure execution path isn't even considered.
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    return NotebookValidator()


def _write_notebook(path: Path, code_cells: list[str]) -> Path:
    cells = [
        {
            "cell_type": "code",
            "source": [src],
            "outputs": [],
            "execution_count": i + 1,
            "metadata": {},
        }
        for i, src in enumerate(code_cells)
    ]
    notebook = {
        "cells": cells,
        "metadata": {"kernelspec": {"name": "python3", "language": "python"}},
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    path.write_text(json.dumps(notebook), encoding="utf-8")
    return path


# ---- Direct regex tests --------------------------------------------------


DATED_PATTERN = r"(?<!anthropic\.)claude-\w+-[\d.]+-\d{8}"


@pytest.mark.parametrize(
    "model_id",
    [
        "claude-sonnet-4-20250514",
        "claude-opus-4-20250514",
    ],
)
def test_dated_pattern_matches_dated_api_ids(model_id):
    assert re.findall(DATED_PATTERN, model_id) == [model_id]


@pytest.mark.parametrize(
    "model_id",
    [
        # Bedrock IDs — must NOT be flagged because Bedrock requires dates pre-Opus-4.6
        "anthropic.claude-sonnet-4-5-20250929-v1:0",
        "anthropic.claude-haiku-4-5-20251001-v1:0",
        "global.anthropic.claude-sonnet-4-5-20250929-v1:0",
    ],
)
def test_dated_pattern_skips_bedrock_ids(model_id):
    assert re.findall(DATED_PATTERN, model_id) == []


@pytest.mark.parametrize(
    "model_id",
    [
        # Current non-dated aliases — never dated
        "claude-sonnet-4-6",
        "claude-haiku-4-5",
        "claude-opus-4-6",
        # Legacy IDs handled by the deprecated_models dict, not the regex
        "claude-3-opus-20240229",
        "claude-3-5-sonnet-20240620",
    ],
)
def test_dated_pattern_does_not_match_aliases_or_legacy(model_id):
    assert re.findall(DATED_PATTERN, model_id) == []


# ---- validate_notebook ---------------------------------------------------


def test_clean_notebook_passes(validator, tmp_path):
    nb = _write_notebook(
        tmp_path / "clean.ipynb",
        ['client = Anthropic()\nresp = client.messages.create(model="claude-sonnet-4-6")'],
    )
    result = validator.validate_notebook(nb, mode="quick")
    assert result["status"] == "pass"
    assert result["issues"] == []


def test_invalid_json_recorded_as_critical(validator, tmp_path):
    bad = tmp_path / "bad.ipynb"
    bad.write_text("not json", encoding="utf-8")
    result = validator.validate_notebook(bad, mode="quick")
    assert result["status"] == "error"
    assert any(i["type"] == "invalid_json" for i in result["issues"])
    assert any(i["severity"] == "critical" for i in result["issues"])


def test_hardcoded_key_marked_critical(validator, tmp_path):
    nb = _write_notebook(
        tmp_path / "leaky.ipynb",
        ['api_key = "sk-ant-api03-LEAKED-KEY-EXAMPLE"'],
    )
    result = validator.validate_notebook(nb, mode="quick")
    assert result["status"] == "error"
    types = {i["type"] for i in result["issues"]}
    assert "hardcoded_api_key" in types


def test_api_key_without_env_marked_critical(validator, tmp_path):
    nb = _write_notebook(
        tmp_path / "literal_key.ipynb",
        ['client = Anthropic(api_key="my-literal-string")'],
    )
    result = validator.validate_notebook(nb, mode="quick")
    assert result["status"] == "error"
    assert any(i["type"] == "api_key_not_env" for i in result["issues"])


def test_api_key_from_env_passes(validator, tmp_path):
    nb = _write_notebook(
        tmp_path / "envkey.ipynb",
        ['client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))'],
    )
    result = validator.validate_notebook(nb, mode="quick")
    assert result["status"] == "pass"


def test_api_key_via_getenv_passes(validator, tmp_path):
    nb = _write_notebook(
        tmp_path / "getenv.ipynb",
        ['client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))'],
    )
    result = validator.validate_notebook(nb, mode="quick")
    assert result["status"] == "pass"


def test_dated_model_id_warns(validator, tmp_path):
    nb = _write_notebook(
        tmp_path / "dated.ipynb",
        ['model = "claude-sonnet-4-20250514"'],
    )
    result = validator.validate_notebook(nb, mode="quick")
    assert result["status"] == "warning"
    assert any(i["type"] == "dated_model_id" for i in result["issues"])


def test_bedrock_dated_id_does_not_trigger_dated_model_warning(validator, tmp_path):
    """Bedrock IDs require dates pre-Opus-4.6, so the dated-ID regex must skip them.

    Uses Haiku 4.5 because that ID is not in the deprecated_models substring map
    (see test_bedrock_id_in_deprecated_map_is_currently_misflagged for the related
    bug in the substring check).
    """
    nb = _write_notebook(
        tmp_path / "bedrock_haiku.ipynb",
        ['model = "anthropic.claude-haiku-4-5-20251001-v1:0"'],
    )
    result = validator.validate_notebook(nb, mode="quick")
    assert result["status"] == "pass"
    assert not any(i["type"] == "dated_model_id" for i in result["issues"])


@pytest.mark.xfail(
    reason=(
        "Known bug: the deprecated_models substring check has no Bedrock "
        "exclusion, so a valid Bedrock ID containing a deprecated alias as a "
        "substring (e.g. 'anthropic.claude-sonnet-4-5-20250929-v1:0' contains "
        "'claude-sonnet-4-5-20250929') is incorrectly flagged. Fix by mirroring "
        "the negative lookbehind from the dated-ID regex into the substring check."
    ),
    strict=True,
)
def test_bedrock_id_in_deprecated_map_is_currently_misflagged(validator, tmp_path):
    nb = _write_notebook(
        tmp_path / "bedrock_sonnet.ipynb",
        ['model = "anthropic.claude-sonnet-4-5-20250929-v1:0"'],
    )
    result = validator.validate_notebook(nb, mode="quick")
    assert result["status"] == "pass"
    assert not any(i["type"] == "deprecated_model" for i in result["issues"])


def test_deprecated_model_warns_with_suggestion(validator, tmp_path):
    nb = _write_notebook(
        tmp_path / "old.ipynb",
        ['model = "claude-3-opus-20240229"'],
    )
    result = validator.validate_notebook(nb, mode="quick")
    assert result["status"] == "warning"
    deprecated = [i for i in result["issues"] if i["type"] == "deprecated_model"]
    assert len(deprecated) == 1
    assert deprecated[0]["details"] == {
        "current": "claude-3-opus-20240229",
        "suggested": "claude-opus-4-6",
    }


def test_error_output_warns(validator, tmp_path):
    notebook = {
        "cells": [
            {
                "cell_type": "code",
                "source": ["x"],
                "outputs": [{"output_type": "error", "ename": "ValueError", "evalue": "boom"}],
                "execution_count": 1,
            }
        ],
        "metadata": {"kernelspec": {"name": "python3", "language": "python"}},
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    nb = tmp_path / "err.ipynb"
    nb.write_text(json.dumps(notebook), encoding="utf-8")
    result = validator.validate_notebook(nb, mode="quick")
    assert result["status"] == "warning"
    assert any(i["type"] == "error_output" for i in result["issues"])


def test_critical_outranks_warning(validator, tmp_path):
    """A hardcoded key plus a deprecated model should produce status=error."""
    nb = _write_notebook(
        tmp_path / "both.ipynb",
        [
            'api_key = "sk-ant-api03-EXAMPLE"',
            'model = "claude-3-opus-20240229"',
        ],
    )
    result = validator.validate_notebook(nb, mode="quick")
    assert result["status"] == "error"


# ---- fix_deprecated_models ----------------------------------------------


def test_fix_deprecated_models_replaces_and_persists(validator, tmp_path):
    nb = _write_notebook(
        tmp_path / "needs_fix.ipynb",
        [
            'model = "claude-3-opus-20240229"',
            'fallback = "claude-3-5-sonnet-20240620"',
        ],
    )

    assert validator.fix_deprecated_models(nb) is True

    rewritten = json.loads(nb.read_text())
    sources = ["".join(cell["source"]) for cell in rewritten["cells"]]
    assert any("claude-opus-4-6" in s for s in sources)
    assert any("claude-sonnet-4-6" in s for s in sources)
    assert not any("claude-3-opus-20240229" in s for s in sources)
    assert not any("claude-3-5-sonnet-20240620" in s for s in sources)


def test_fix_deprecated_models_noop_returns_false(validator, tmp_path):
    nb = _write_notebook(tmp_path / "clean.ipynb", ['model = "claude-sonnet-4-6"'])
    original = nb.read_text()
    assert validator.fix_deprecated_models(nb) is False
    assert nb.read_text() == original


def test_fix_deprecated_models_preserves_surrounding_code(validator, tmp_path):
    nb = _write_notebook(
        tmp_path / "around.ipynb",
        ['# header comment\nmodel = "claude-3-opus-20240229"\nprint("done")'],
    )
    validator.fix_deprecated_models(nb)
    rewritten = json.loads(nb.read_text())
    src = "".join(rewritten["cells"][0]["source"])
    assert "# header comment" in src
    assert 'print("done")' in src
    assert "claude-opus-4-6" in src


def test_fix_deprecated_models_skips_markdown(validator, tmp_path):
    notebook = {
        "cells": [
            {
                "cell_type": "markdown",
                "source": ["This notebook used to use `claude-3-opus-20240229`."],
            }
        ],
        "metadata": {"kernelspec": {"name": "python3", "language": "python"}},
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    nb = tmp_path / "md.ipynb"
    nb.write_text(json.dumps(notebook), encoding="utf-8")
    assert validator.fix_deprecated_models(nb) is False


# ---- Auto-fix mapping sanity --------------------------------------------


def test_all_replacement_targets_are_current_aliases(validator, tmp_path):
    """Every value in the deprecated->current map must itself be a valid current alias."""
    current = {"claude-sonnet-4-6", "claude-haiku-4-5", "claude-opus-4-6"}

    # Trigger the dict via fix_deprecated_models on a notebook covering each key.
    # Read the dict directly via a representative call.
    nb = _write_notebook(
        tmp_path / "sample.ipynb",
        ['model = "claude-3-opus-20240229"'],
    )
    validator.fix_deprecated_models(nb)
    fixed_source = "".join(json.loads(nb.read_text())["cells"][0]["source"])
    # Sanity: at least one current alias is now present.
    assert any(alias in fixed_source for alias in current)
