"""Tests for .github/scripts/verify_registry.py.

These tests focus on the core validation logic without making network calls.
Network calls are mocked to test error handling and response processing.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add scripts directory to path to import the module
SCRIPTS_DIR = Path(__file__).parent.parent / ".github" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import verify_registry  # noqa: E402


@pytest.fixture
def mock_response():
    """Create a mock requests response."""

    def _make_response(status_code: int, **kwargs):
        response = MagicMock()
        response.status_code = status_code
        for key, value in kwargs.items():
            setattr(response, key, value)
        return response

    return _make_response


class TestCheckGithubHandle:
    """Tests for check_github_handle function."""

    @patch("verify_registry.requests.head")
    def test_valid_handle(self, mock_head, mock_response):
        """Test successful validation of a GitHub handle."""
        mock_head.return_value = mock_response(200)

        success, error = verify_registry.check_github_handle("octocat")

        assert success is True
        assert error is None
        mock_head.assert_called_once()
        assert "github.com/octocat" in mock_head.call_args[0][0]

    @patch("verify_registry.requests.head")
    def test_handle_not_found(self, mock_head, mock_response):
        """Test handling of non-existent GitHub handle."""
        mock_head.return_value = mock_response(404)

        success, error = verify_registry.check_github_handle("nonexistentuser123456789")

        assert success is False
        assert "not found" in error

    @patch("verify_registry.requests.head")
    def test_http_error(self, mock_head, mock_response):
        """Test handling of HTTP errors."""
        mock_head.return_value = mock_response(500)

        success, error = verify_registry.check_github_handle("testuser")

        assert success is False
        assert "500" in error

    @patch("verify_registry.requests.head")
    def test_request_exception(self, mock_head):
        """Test handling of request exceptions."""
        mock_head.side_effect = Exception("Network error")

        success, error = verify_registry.check_github_handle("testuser")

        assert success is False
        assert "Network error" in error


class TestCheckUrl:
    """Tests for check_url function."""

    @patch("verify_registry.requests.head")
    def test_valid_url(self, mock_head, mock_response):
        """Test successful URL validation."""
        mock_head.return_value = mock_response(200)

        success, error = verify_registry.check_url("https://example.com")

        assert success is True
        assert error is None

    @patch("verify_registry.requests.head")
    def test_url_not_found(self, mock_head, mock_response):
        """Test handling of 404 URLs."""
        mock_head.return_value = mock_response(404)

        success, error = verify_registry.check_url("https://example.com/notfound")

        assert success is False
        assert "404" in error

    def test_x_com_url_skipped(self):
        """Test that x.com URLs are skipped (they block HEAD requests)."""
        success, error = verify_registry.check_url("https://x.com/username")

        assert success is True
        assert "skipped" in error

    @patch("verify_registry.requests.head")
    def test_request_exception(self, mock_head):
        """Test handling of request exceptions."""
        mock_head.side_effect = Exception("Timeout")

        success, error = verify_registry.check_url("https://example.com")

        assert success is False
        assert "Timeout" in error


class TestVerifyAuthors:
    """Tests for verify_authors function."""

    @patch("verify_registry.check_github_handle")
    @patch("verify_registry.check_url")
    def test_all_valid(self, mock_check_url, mock_check_handle, capsys):
        """Test verification of all valid authors."""
        mock_check_handle.return_value = (True, None)
        mock_check_url.return_value = (True, None)

        authors = {
            "alice": {"name": "Alice", "website": "https://alice.com", "avatar": "https://avatar.com/alice.png"}
        }

        failed_handles, failed_urls = verify_registry.verify_authors(authors)

        assert failed_handles == []
        assert failed_urls == []

    @patch("verify_registry.check_github_handle")
    @patch("verify_registry.check_url")
    def test_invalid_handle(self, mock_check_url, mock_check_handle, capsys):
        """Test handling of invalid GitHub handle."""
        mock_check_handle.return_value = (False, "not found")
        mock_check_url.return_value = (True, None)

        authors = {"baduser": {"name": "Bad User"}}

        failed_handles, failed_urls = verify_registry.verify_authors(authors)

        assert len(failed_handles) == 1
        assert "baduser" in failed_handles[0]

    @patch("verify_registry.check_github_handle")
    @patch("verify_registry.check_url")
    def test_invalid_url(self, mock_check_url, mock_check_handle, capsys):
        """Test handling of invalid URLs."""
        mock_check_handle.return_value = (True, None)
        mock_check_url.return_value = (False, "404")

        authors = {"alice": {"name": "Alice", "website": "https://broken.com"}}

        failed_handles, failed_urls = verify_registry.verify_authors(authors)

        assert len(failed_urls) == 1
        assert "broken.com" in failed_urls[0]


class TestVerifyRegistryAuthors:
    """Tests for verify_registry_authors function."""

    def test_all_authors_exist(self, capsys):
        """Test when all registry authors exist in authors.yaml."""
        registry = [
            {"title": "Example", "authors": ["alice", "bob"]},
            {"title": "Another", "authors": ["alice"]},
        ]
        authors = {"alice": {}, "bob": {}, "charlie": {}}

        missing = verify_registry.verify_registry_authors(registry, authors)

        assert missing == []

    def test_missing_author(self, capsys):
        """Test detection of missing authors."""
        registry = [{"title": "Example", "authors": ["alice", "missing"]}]
        authors = {"alice": {}}

        missing = verify_registry.verify_registry_authors(registry, authors)

        assert len(missing) == 1
        assert "missing" in missing

    def test_empty_registry(self, capsys):
        """Test handling of empty registry."""
        missing = verify_registry.verify_registry_authors([], {"alice": {}})
        assert missing == []

    def test_entry_without_authors_field(self, capsys):
        """Test handling of entries without authors field."""
        registry = [{"title": "Example"}]
        authors = {"alice": {}}

        # Should not crash, just skip entries without authors
        missing = verify_registry.verify_registry_authors(registry, authors)
        assert missing == []


class TestVerifyPaths:
    """Tests for verify_paths function."""

    def test_all_paths_exist(self, tmp_path: Path, capsys):
        """Test when all registry paths exist."""
        notebook1 = tmp_path / "example.ipynb"
        notebook1.write_text("{}")
        notebook2 = tmp_path / "another.ipynb"
        notebook2.write_text("{}")

        registry = [
            {"title": "Example", "path": "example.ipynb"},
            {"title": "Another", "path": "another.ipynb"},
        ]

        missing = verify_registry.verify_paths(registry, tmp_path)
        assert missing == []

    def test_missing_path(self, tmp_path: Path, capsys):
        """Test detection of missing paths."""
        existing = tmp_path / "exists.ipynb"
        existing.write_text("{}")

        registry = [
            {"title": "Exists", "path": "exists.ipynb"},
            {"title": "Missing", "path": "missing.ipynb"},
        ]

        missing = verify_registry.verify_paths(registry, tmp_path)

        assert len(missing) == 1
        assert "missing.ipynb" in missing[0]

    def test_entry_without_path_field(self, tmp_path: Path, capsys):
        """Test handling of entries without path field."""
        registry = [{"title": "No Path"}]

        missing = verify_registry.verify_paths(registry, tmp_path)

        assert len(missing) == 1
        assert "missing 'path' field" in missing[0]


class TestVerifySchemas:
    """Tests for verify_schemas function (when jsonschema is available)."""

    def test_skips_when_jsonschema_unavailable(self, tmp_path: Path, capsys, monkeypatch):
        """Test graceful handling when jsonschema is not installed."""
        # Temporarily disable jsonschema
        monkeypatch.setattr(verify_registry, "HAS_JSONSCHEMA", False)

        errors = verify_registry.verify_schemas(tmp_path, {}, [])

        assert errors == []
        captured = capsys.readouterr()
        assert "Skipping schema validation" in captured.out

    @pytest.mark.skipif(not verify_registry.HAS_JSONSCHEMA, reason="jsonschema not installed")
    def test_missing_schema_files(self, tmp_path: Path, capsys):
        """Test handling when schema files don't exist."""
        errors = verify_registry.verify_schemas(tmp_path, {}, [])

        assert errors == []
        captured = capsys.readouterr()
        # Should skip if schemas don't exist
        assert "not found" in captured.out


class TestMain:
    """Tests for main function."""

    @patch("verify_registry.verify_authors")
    @patch("verify_registry.verify_registry_authors")
    @patch("verify_registry.verify_paths")
    @patch("verify_registry.verify_schemas")
    def test_all_command_success(
        self,
        mock_schemas,
        mock_paths,
        mock_registry,
        mock_authors,
        tmp_path: Path,
        capsys,
        monkeypatch,
    ):
        """Test successful 'all' command."""
        # Setup mocks to return no errors
        mock_authors.return_value = ([], [])
        mock_registry.return_value = []
        mock_paths.return_value = []
        mock_schemas.return_value = []

        # Create temporary YAML files
        authors_file = tmp_path / "authors.yaml"
        authors_file.write_text("alice:\n  name: Alice")
        registry_file = tmp_path / "registry.yaml"
        registry_file.write_text("- title: Test\n  path: test.ipynb")

        with patch.object(sys, "argv", ["verify_registry.py", "all"]):
            with patch("builtins.open", side_effect=lambda f, *args, **kwargs: open(f, *args, **kwargs)):
                # Patch the file paths
                monkeypatch.chdir(tmp_path)
                with pytest.raises(SystemExit) as exc:
                    with patch("verify_registry.Path") as mock_path:
                        mock_path.return_value.parent.parent.parent = tmp_path
                        verify_registry.main()
                assert exc.value.code == 0

    def test_invalid_command(self, capsys):
        """Test handling of invalid command."""
        with patch.object(sys, "argv", ["verify_registry.py", "invalid"]):
            with pytest.raises(SystemExit) as exc:
                verify_registry.main()
            assert exc.value.code == 1

        captured = capsys.readouterr()
        assert "Unknown command" in captured.out
