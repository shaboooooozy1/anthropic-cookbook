"""Tests for scripts/validate_notebooks.py."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Add scripts directory to path to import the module
SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import validate_notebooks  # noqa: E402


class TestValidateNotebook:
    """Tests for validate_notebook function."""

    def test_valid_notebook_no_issues(self, tmp_path: Path):
        """Test that a valid notebook returns no issues."""
        nb = {
            "cells": [
                {
                    "cell_type": "code",
                    "execution_count": 1,
                    "source": ["print('hello')"],
                    "outputs": [],
                }
            ]
        }
        nb_path = tmp_path / "valid.ipynb"
        nb_path.write_text(json.dumps(nb))

        issues = validate_notebooks.validate_notebook(nb_path)
        assert issues == []

    def test_empty_cell_detected(self, tmp_path: Path):
        """Test that empty cells are detected."""
        nb = {
            "cells": [
                {"cell_type": "code", "execution_count": 1, "source": [], "outputs": []},
                {"cell_type": "markdown", "source": []},
            ]
        }
        nb_path = tmp_path / "empty.ipynb"
        nb_path.write_text(json.dumps(nb))

        issues = validate_notebooks.validate_notebook(nb_path)
        assert len(issues) == 2
        assert "Empty cell found" in issues[0]
        assert "Empty cell found" in issues[1]

    def test_error_output_detected(self, tmp_path: Path):
        """Test that error outputs are detected."""
        nb = {
            "cells": [
                {
                    "cell_type": "code",
                    "execution_count": 1,
                    "source": ["1/0"],
                    "outputs": [
                        {
                            "output_type": "error",
                            "ename": "ZeroDivisionError",
                            "evalue": "division by zero",
                        }
                    ],
                }
            ]
        }
        nb_path = tmp_path / "error.ipynb"
        nb_path.write_text(json.dumps(nb))

        issues = validate_notebooks.validate_notebook(nb_path)
        assert len(issues) == 1
        assert "Contains error output" in issues[0]

    def test_multiple_errors_in_single_notebook(self, tmp_path: Path):
        """Test that multiple errors are detected."""
        nb = {
            "cells": [
                {"cell_type": "code", "execution_count": 1, "source": [], "outputs": []},
                {
                    "cell_type": "code",
                    "execution_count": 2,
                    "source": ["error"],
                    "outputs": [{"output_type": "error", "ename": "X", "evalue": "y"}],
                },
            ]
        }
        nb_path = tmp_path / "multi.ipynb"
        nb_path.write_text(json.dumps(nb))

        issues = validate_notebooks.validate_notebook(nb_path)
        assert len(issues) == 2

    def test_cells_with_content_pass(self, tmp_path: Path):
        """Test that cells with content do not trigger issues."""
        nb = {
            "cells": [
                {
                    "cell_type": "code",
                    "execution_count": 1,
                    "source": ["import os\n", "print('test')"],
                    "outputs": [],
                },
                {"cell_type": "markdown", "source": ["# Title\n", "Content here"]},
            ]
        }
        nb_path = tmp_path / "content.ipynb"
        nb_path.write_text(json.dumps(nb))

        issues = validate_notebooks.validate_notebook(nb_path)
        assert issues == []


class TestMain:
    """Tests for main function."""

    def test_no_notebooks_provided(self, capsys):
        """Test handling when no notebooks are provided."""
        with patch.object(sys, "argv", ["validate_notebooks.py"]):
            with pytest.raises(SystemExit) as exc:
                validate_notebooks.main()
            assert exc.value.code == 0

        captured = capsys.readouterr()
        assert "No notebooks to validate" in captured.out

    def test_non_notebook_files_ignored(self, tmp_path: Path, capsys):
        """Test that non-.ipynb files are ignored."""
        txt_file = tmp_path / "readme.txt"
        txt_file.write_text("not a notebook")

        with patch.object(sys, "argv", ["validate_notebooks.py", str(txt_file)]):
            with pytest.raises(SystemExit) as exc:
                validate_notebooks.main()
            assert exc.value.code == 0

        captured = capsys.readouterr()
        assert "No notebooks to validate" in captured.out

    def test_valid_notebook_succeeds(self, tmp_path: Path, capsys):
        """Test successful validation of a valid notebook."""
        nb = {
            "cells": [
                {
                    "cell_type": "code",
                    "execution_count": 1,
                    "source": ["x = 1"],
                    "outputs": [],
                }
            ]
        }
        nb_path = tmp_path / "valid.ipynb"
        nb_path.write_text(json.dumps(nb))

        with patch.object(sys, "argv", ["validate_notebooks.py", str(nb_path)]):
            with pytest.raises(SystemExit) as exc:
                validate_notebooks.main()
            assert exc.value.code == 0

        captured = capsys.readouterr()
        assert "validated successfully" in captured.out

    def test_invalid_notebook_fails(self, tmp_path: Path, capsys):
        """Test that invalid notebooks cause exit with error code."""
        nb = {"cells": [{"cell_type": "code", "execution_count": 1, "source": [], "outputs": []}]}
        nb_path = tmp_path / "empty.ipynb"
        nb_path.write_text(json.dumps(nb))

        with patch.object(sys, "argv", ["validate_notebooks.py", str(nb_path)]):
            with pytest.raises(SystemExit) as exc:
                validate_notebooks.main()
            assert exc.value.code == 1

        captured = capsys.readouterr()
        assert "Found issues" in captured.out
        assert "Empty cell found" in captured.out

    def test_multiple_notebooks_mixed_validity(self, tmp_path: Path, capsys):
        """Test validation with mix of valid and invalid notebooks."""
        # Valid notebook
        valid_nb = {
            "cells": [
                {
                    "cell_type": "code",
                    "execution_count": 1,
                    "source": ["x = 1"],
                    "outputs": [],
                }
            ]
        }
        valid_path = tmp_path / "valid.ipynb"
        valid_path.write_text(json.dumps(valid_nb))

        # Invalid notebook
        invalid_nb = {"cells": [{"cell_type": "code", "source": [], "outputs": []}]}
        invalid_path = tmp_path / "invalid.ipynb"
        invalid_path.write_text(json.dumps(invalid_nb))

        with patch.object(sys, "argv", ["validate_notebooks.py", str(valid_path), str(invalid_path)]):
            with pytest.raises(SystemExit) as exc:
                validate_notebooks.main()
            assert exc.value.code == 1

        captured = capsys.readouterr()
        assert "invalid.ipynb" in captured.out
        assert "Empty cell found" in captured.out
