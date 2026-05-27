"""Tests for scripts/validate_authors_sorted.py."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

# Add scripts directory to path to import the module
SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import validate_authors_sorted  # noqa: E402


@pytest.fixture
def temp_authors_file(tmp_path: Path, monkeypatch):
    """Create a temporary authors.yaml file for testing."""
    authors_path = tmp_path / "authors.yaml"
    # Patch the AUTHORS_FILE constant to use our temp file
    monkeypatch.setattr(validate_authors_sorted, "AUTHORS_FILE", authors_path)
    return authors_path


class TestLoadAuthors:
    """Tests for load_authors function."""

    def test_load_valid_authors(self, temp_authors_file):
        """Test loading a valid authors.yaml file."""
        data = {"alice": {"name": "Alice Smith"}, "bob": {"name": "Bob Jones"}}
        temp_authors_file.write_text(yaml.dump(data))

        result = validate_authors_sorted.load_authors()
        assert result == data

    def test_load_empty_file(self, temp_authors_file):
        """Test loading an empty authors.yaml file."""
        temp_authors_file.write_text("")

        result = validate_authors_sorted.load_authors()
        assert result is None


class TestIsSorted:
    """Tests for is_sorted function."""

    def test_sorted_alphabetically(self):
        """Test that alphabetically sorted data is detected as sorted."""
        data = {"alice": {}, "bob": {}, "charlie": {}}
        assert validate_authors_sorted.is_sorted(data) is True

    def test_sorted_case_insensitive(self):
        """Test case-insensitive sorting detection."""
        data = {"Alice": {}, "bob": {}, "Charlie": {}}
        assert validate_authors_sorted.is_sorted(data) is True

    def test_unsorted_data(self):
        """Test that unsorted data is detected."""
        data = {"charlie": {}, "alice": {}, "bob": {}}
        assert validate_authors_sorted.is_sorted(data) is False

    def test_empty_dict(self):
        """Test that an empty dict is considered sorted."""
        assert validate_authors_sorted.is_sorted({}) is True

    def test_single_entry(self):
        """Test that a single entry is considered sorted."""
        assert validate_authors_sorted.is_sorted({"alice": {}}) is True


class TestSortAuthors:
    """Tests for sort_authors function."""

    def test_check_only_mode_no_changes(self, temp_authors_file):
        """Test check_only mode with already sorted data."""
        data = {"alice": {"name": "Alice"}, "bob": {"name": "Bob"}}
        temp_authors_file.write_text(yaml.dump(data))

        changed = validate_authors_sorted.sort_authors(data, check_only=True)
        assert changed is False

    def test_check_only_mode_needs_changes(self, temp_authors_file):
        """Test check_only mode with unsorted data."""
        data = {"charlie": {"name": "Charlie"}, "alice": {"name": "Alice"}}
        temp_authors_file.write_text(yaml.dump(data))

        changed = validate_authors_sorted.sort_authors(data, check_only=True)
        assert changed is True

    def test_writes_sorted_data(self, temp_authors_file):
        """Test that sort_authors actually sorts and writes data."""
        data = {"charlie": {"name": "Charlie"}, "alice": {"name": "Alice"}, "bob": {"name": "Bob"}}

        validate_authors_sorted.sort_authors(data, check_only=False)

        # Read back the file
        with open(temp_authors_file) as f:
            content = f.read()

        assert content.startswith(validate_authors_sorted.HEADER)
        # Check that the data appears in sorted order in the file
        alice_pos = content.index("alice:")
        bob_pos = content.index("bob:")
        charlie_pos = content.index("charlie:")
        assert alice_pos < bob_pos < charlie_pos

    def test_preserves_header(self, temp_authors_file):
        """Test that the header comment is preserved."""
        data = {"alice": {"name": "Alice"}}

        validate_authors_sorted.sort_authors(data, check_only=False)

        content = temp_authors_file.read_text()
        assert validate_authors_sorted.HEADER in content

    def test_case_insensitive_sort(self, temp_authors_file):
        """Test that sorting is case-insensitive."""
        data = {"Charlie": {"name": "C"}, "alice": {"name": "A"}, "Bob": {"name": "B"}}

        validate_authors_sorted.sort_authors(data, check_only=False)

        # Verify order in file
        content = temp_authors_file.read_text()
        alice_pos = content.index("alice:")
        bob_pos = content.index("Bob:")
        charlie_pos = content.index("Charlie:")
        assert alice_pos < bob_pos < charlie_pos


class TestShowDiff:
    """Tests for show_diff function."""

    def test_shows_current_and_expected_order(self, capsys):
        """Test that diff shows both current and expected order."""
        keys = ["charlie", "alice", "bob"]
        sorted_keys = ["alice", "bob", "charlie"]

        validate_authors_sorted.show_diff(keys, sorted_keys)

        captured = capsys.readouterr()
        assert "Current order:" in captured.out
        assert "Expected order:" in captured.out
        assert "charlie" in captured.out
        assert "alice" in captured.out
        assert "bob" in captured.out

    def test_shows_out_of_place_entries(self, capsys):
        """Test that diff highlights out-of-place entries."""
        keys = ["charlie", "alice"]
        sorted_keys = ["alice", "charlie"]

        validate_authors_sorted.show_diff(keys, sorted_keys)

        captured = capsys.readouterr()
        assert "Out of place entries:" in captured.out


class TestMain:
    """Tests for main function."""

    def test_validation_mode_sorted_file(self, temp_authors_file, capsys):
        """Test validation mode with already sorted file."""
        data = {"alice": {"name": "Alice"}, "bob": {"name": "Bob"}}
        temp_authors_file.write_text(yaml.dump(data))

        with patch.object(sys, "argv", ["validate_authors_sorted.py"]):
            with pytest.raises(SystemExit) as exc:
                validate_authors_sorted.main()
            assert exc.value.code == 0

        captured = capsys.readouterr()
        assert "1 file left unchanged" in captured.out

    def test_validation_mode_unsorted_file(self, temp_authors_file, capsys):
        """Test validation mode with unsorted file fails."""
        data = {"charlie": {"name": "Charlie"}, "alice": {"name": "Alice"}}
        temp_authors_file.write_text(yaml.dump(data))

        with patch.object(sys, "argv", ["validate_authors_sorted.py"]):
            with pytest.raises(SystemExit) as exc:
                validate_authors_sorted.main()
            assert exc.value.code == 1

        captured = capsys.readouterr()
        assert "not sorted" in captured.out

    def test_fix_mode_sorted_file(self, temp_authors_file, capsys):
        """Test fix mode with already sorted file."""
        data = {"alice": {"name": "Alice"}, "bob": {"name": "Bob"}}
        temp_authors_file.write_text(yaml.dump(data))

        with patch.object(sys, "argv", ["validate_authors_sorted.py", "--fix"]):
            with pytest.raises(SystemExit) as exc:
                validate_authors_sorted.main()
            assert exc.value.code == 0

        captured = capsys.readouterr()
        assert "1 file left unchanged" in captured.out

    def test_fix_mode_sorts_file(self, temp_authors_file, capsys):
        """Test fix mode actually sorts the file."""
        data = {"charlie": {"name": "Charlie"}, "alice": {"name": "Alice"}}
        temp_authors_file.write_text(yaml.dump(data))

        with patch.object(sys, "argv", ["validate_authors_sorted.py", "--fix"]):
            with pytest.raises(SystemExit) as exc:
                validate_authors_sorted.main()
            assert exc.value.code == 0

        captured = capsys.readouterr()
        assert "1 file reformatted" in captured.out

        # Verify file is now sorted
        with open(temp_authors_file) as f:
            content = f.read()
        alice_pos = content.index("alice:")
        charlie_pos = content.index("charlie:")
        assert alice_pos < charlie_pos

    def test_empty_authors_file(self, temp_authors_file, capsys):
        """Test handling of empty authors.yaml."""
        temp_authors_file.write_text("")

        with patch.object(sys, "argv", ["validate_authors_sorted.py"]):
            with pytest.raises(SystemExit) as exc:
                validate_authors_sorted.main()
            assert exc.value.code == 0

        captured = capsys.readouterr()
        assert "authors.yaml is empty" in captured.out
