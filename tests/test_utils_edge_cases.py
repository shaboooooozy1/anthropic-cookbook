"""Additional edge case tests for tests/notebook_tests/utils.py.

These tests supplement test_utils.py with additional coverage for edge cases
and integration scenarios.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tests.notebook_tests.utils import (
    NotebookValidationResult,
    execute_notebook,
    find_all_notebooks,
    validate_notebook_structure,
)


class TestNotebookValidationResult:
    """Tests for NotebookValidationResult dataclass."""

    def test_initial_state(self):
        """Test initial state of validation result."""
        result = NotebookValidationResult(path=Path("test.ipynb"))
        assert result.is_valid is True
        assert result.errors == []
        assert result.warnings == []
        assert result.info == []

    def test_add_error_sets_invalid(self):
        """Test that adding an error marks result as invalid."""
        result = NotebookValidationResult(path=Path("test.ipynb"))
        result.add_error("Error occurred")
        assert result.is_valid is False
        assert "Error occurred" in result.errors

    def test_add_warning_does_not_invalidate(self):
        """Test that warnings don't affect validity."""
        result = NotebookValidationResult(path=Path("test.ipynb"))
        result.add_warning("Warning message")
        assert result.is_valid is True
        assert "Warning message" in result.warnings

    def test_add_info(self):
        """Test adding informational messages."""
        result = NotebookValidationResult(path=Path("test.ipynb"))
        result.add_info("Info message")
        assert result.is_valid is True
        assert "Info message" in result.info


class TestValidateNotebookStructure:
    """Integration tests for validate_notebook_structure function."""

    def test_valid_notebook(self, tmp_path: Path):
        """Test validation of a completely valid notebook."""
        nb = {
            "cells": [
                {
                    "cell_type": "markdown",
                    "source": ["# Title"],
                },
                {
                    "cell_type": "code",
                    "execution_count": 1,
                    "source": ["import os\n", 'client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])'],
                    "outputs": [],
                },
            ]
        }
        nb_path = tmp_path / "valid.ipynb"
        nb_path.write_text(json.dumps(nb))

        result = validate_notebook_structure(nb_path)

        assert result.is_valid is True
        assert len(result.errors) == 0
        assert len(result.cells) == 2

    def test_invalid_json(self, tmp_path: Path):
        """Test handling of invalid JSON."""
        nb_path = tmp_path / "invalid.ipynb"
        nb_path.write_text("{invalid json")

        result = validate_notebook_structure(nb_path)

        assert result.is_valid is False
        assert any("Invalid JSON" in e for e in result.errors)

    def test_file_not_found(self):
        """Test handling of non-existent file."""
        result = validate_notebook_structure(Path("/nonexistent.ipynb"))

        assert result.is_valid is False
        assert any("not found" in e for e in result.errors)

    def test_multiple_validation_errors(self, tmp_path: Path):
        """Test notebook with multiple validation issues."""
        nb = {
            "cells": [
                {"cell_type": "code", "execution_count": None, "source": ["x=1"], "outputs": []},
                {
                    "cell_type": "code",
                    "execution_count": 1,
                    "source": ["error"],
                    "outputs": [{"output_type": "error"}],
                },
                {
                    "cell_type": "code",
                    "execution_count": 1,
                    "source": ['key="sk-ant-api03-test"'],
                    "outputs": [],
                },
            ]
        }
        nb_path = tmp_path / "multi_error.ipynb"
        nb_path.write_text(json.dumps(nb))

        result = validate_notebook_structure(nb_path)

        assert result.is_valid is False
        assert len(result.errors) > 1

    def test_warnings_do_not_fail_validation(self, tmp_path: Path):
        """Test that warnings don't mark notebook as invalid."""
        nb = {
            "cells": [
                {"cell_type": "code", "execution_count": 1, "source": [""], "outputs": []},
                {
                    "cell_type": "code",
                    "execution_count": 2,
                    "source": ['client = Anthropic(api_key="placeholder")'],
                    "outputs": [],
                },
            ]
        }
        nb_path = tmp_path / "warnings.ipynb"
        nb_path.write_text(json.dumps(nb))

        result = validate_notebook_structure(nb_path)

        # Should be valid despite warnings
        assert result.is_valid is True
        assert len(result.warnings) > 0


class TestExecuteNotebook:
    """Tests for execute_notebook function."""

    def test_timeout_parameter(self, tmp_path: Path):
        """Test that timeout parameter is used correctly."""
        nb = {
            "cells": [
                {"cell_type": "code", "execution_count": 1, "source": ["print(1)"], "outputs": []}
            ],
            "metadata": {"kernelspec": {"name": "python3"}},
            "nbformat": 4,
            "nbformat_minor": 5,
        }
        nb_path = tmp_path / "test.ipynb"
        nb_path.write_text(json.dumps(nb))

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            success, message, output_path = execute_notebook(nb_path, timeout=120)

            # Verify timeout was passed to subprocess
            call_args = mock_run.call_args[0][0]
            assert any("timeout=120" in str(arg) for arg in call_args)

    def test_kernel_name_parameter(self, tmp_path: Path):
        """Test that kernel_name parameter is used."""
        nb = {
            "cells": [],
            "metadata": {"kernelspec": {"name": "python3"}},
            "nbformat": 4,
            "nbformat_minor": 5,
        }
        nb_path = tmp_path / "test.ipynb"
        nb_path.write_text(json.dumps(nb))

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            execute_notebook(nb_path, kernel_name="custom_kernel")

            call_args = mock_run.call_args[0][0]
            assert any("kernel_name=custom_kernel" in str(arg) for arg in call_args)

    def test_allow_errors_parameter(self, tmp_path: Path):
        """Test that allow_errors parameter is passed."""
        nb = {"cells": [], "metadata": {}, "nbformat": 4, "nbformat_minor": 5}
        nb_path = tmp_path / "test.ipynb"
        nb_path.write_text(json.dumps(nb))

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            execute_notebook(nb_path, allow_errors=True)

            call_args = mock_run.call_args[0][0]
            assert "--allow-errors" in call_args

    def test_execution_failure(self, tmp_path: Path):
        """Test handling of execution failure."""
        nb = {"cells": [], "metadata": {}, "nbformat": 4, "nbformat_minor": 5}
        nb_path = tmp_path / "test.ipynb"
        nb_path.write_text(json.dumps(nb))

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stderr="Execution failed")

            success, message, output_path = execute_notebook(nb_path)

            assert success is False
            assert "failed" in message.lower()

    def test_timeout_expired(self, tmp_path: Path):
        """Test handling of execution timeout."""
        nb = {"cells": [], "metadata": {}, "nbformat": 4, "nbformat_minor": 5}
        nb_path = tmp_path / "test.ipynb"
        nb_path.write_text(json.dumps(nb))

        with patch("subprocess.run") as mock_run:
            import subprocess

            mock_run.side_effect = subprocess.TimeoutExpired("cmd", 10)

            success, message, output_path = execute_notebook(nb_path, timeout=10)

            assert success is False
            assert "timed out" in message.lower()
            assert output_path is None

    def test_general_exception(self, tmp_path: Path):
        """Test handling of general exceptions."""
        nb = {"cells": [], "metadata": {}, "nbformat": 4, "nbformat_minor": 5}
        nb_path = tmp_path / "test.ipynb"
        nb_path.write_text(json.dumps(nb))

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = RuntimeError("Unexpected error")

            success, message, output_path = execute_notebook(nb_path)

            assert success is False
            assert "error" in message.lower()
            assert output_path is None


class TestFindAllNotebooks:
    """Tests for find_all_notebooks function."""

    def test_finds_notebooks_recursively(self, tmp_path: Path):
        """Test finding notebooks in nested directories."""
        (tmp_path / "dir1").mkdir()
        (tmp_path / "dir1" / "nb1.ipynb").write_text("{}")
        (tmp_path / "dir2").mkdir()
        (tmp_path / "dir2" / "nb2.ipynb").write_text("{}")
        (tmp_path / "nb3.ipynb").write_text("{}")

        notebooks = find_all_notebooks(tmp_path)

        assert len(notebooks) == 3
        paths = [nb.name for nb in notebooks]
        assert "nb1.ipynb" in paths
        assert "nb2.ipynb" in paths
        assert "nb3.ipynb" in paths

    def test_excludes_checkpoint_files(self, tmp_path: Path):
        """Test that checkpoint files are excluded."""
        (tmp_path / ".ipynb_checkpoints").mkdir()
        (tmp_path / ".ipynb_checkpoints" / "checkpoint.ipynb").write_text("{}")
        (tmp_path / "regular.ipynb").write_text("{}")

        notebooks = find_all_notebooks(tmp_path)

        assert len(notebooks) == 1
        assert notebooks[0].name == "regular.ipynb"

    def test_exclude_patterns(self, tmp_path: Path):
        """Test exclude patterns functionality."""
        (tmp_path / "include.ipynb").write_text("{}")
        (tmp_path / "exclude.ipynb").write_text("{}")
        (tmp_path / "test").mkdir()
        (tmp_path / "test" / "test.ipynb").write_text("{}")

        notebooks = find_all_notebooks(tmp_path, exclude_patterns=["exclude.ipynb", "test/*.ipynb"])

        assert len(notebooks) == 1
        assert notebooks[0].name == "include.ipynb"

    def test_empty_directory(self, tmp_path: Path):
        """Test handling of directory with no notebooks."""
        notebooks = find_all_notebooks(tmp_path)
        assert notebooks == []

    def test_returns_sorted_list(self, tmp_path: Path):
        """Test that results are sorted."""
        (tmp_path / "c.ipynb").write_text("{}")
        (tmp_path / "a.ipynb").write_text("{}")
        (tmp_path / "b.ipynb").write_text("{}")

        notebooks = find_all_notebooks(tmp_path)

        names = [nb.name for nb in notebooks]
        assert names == ["a.ipynb", "b.ipynb", "c.ipynb"]

    def test_non_notebook_files_ignored(self, tmp_path: Path):
        """Test that non-.ipynb files are ignored."""
        (tmp_path / "notebook.ipynb").write_text("{}")
        (tmp_path / "readme.md").write_text("# README")
        (tmp_path / "script.py").write_text("print('hi')")

        notebooks = find_all_notebooks(tmp_path)

        assert len(notebooks) == 1
        assert notebooks[0].name == "notebook.ipynb"


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_notebook_with_very_long_cell(self, tmp_path: Path):
        """Test handling of notebooks with very long cells."""
        long_source = ["x = 1\n"] * 10000  # Very long cell
        nb = {
            "cells": [
                {
                    "cell_type": "code",
                    "execution_count": 1,
                    "source": long_source,
                    "outputs": [],
                }
            ]
        }
        nb_path = tmp_path / "long.ipynb"
        nb_path.write_text(json.dumps(nb))

        result = validate_notebook_structure(nb_path)
        # Should handle gracefully without errors
        assert len(result.cells) == 1

    def test_notebook_with_unicode_content(self, tmp_path: Path):
        """Test handling of notebooks with unicode characters."""
        nb = {
            "cells": [
                {
                    "cell_type": "code",
                    "execution_count": 1,
                    "source": ["print('Hello 世界 🌍')"],
                    "outputs": [],
                }
            ]
        }
        nb_path = tmp_path / "unicode.ipynb"
        nb_path.write_text(json.dumps(nb, ensure_ascii=False), encoding="utf-8")

        result = validate_notebook_structure(nb_path)
        assert result.is_valid is True

    def test_notebook_with_null_execution_counts(self, tmp_path: Path):
        """Test notebooks where execution_count is explicitly null."""
        nb = {
            "cells": [
                {
                    "cell_type": "code",
                    "execution_count": None,
                    "source": ["print('test')"],
                    "outputs": [],
                }
            ]
        }
        nb_path = tmp_path / "null_exec.ipynb"
        nb_path.write_text(json.dumps(nb))

        result = validate_notebook_structure(nb_path)
        # Should detect unexecuted cell
        assert not result.is_valid

    def test_empty_notebook(self, tmp_path: Path):
        """Test completely empty notebook."""
        nb = {"cells": []}
        nb_path = tmp_path / "empty.ipynb"
        nb_path.write_text(json.dumps(nb))

        result = validate_notebook_structure(nb_path)
        # Empty notebook is technically valid (no errors)
        assert len(result.cells) == 0
