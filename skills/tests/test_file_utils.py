"""Tests for ``skills/file_utils.py`` — Files API helpers used by the Skills notebooks.

These exercise the pure-logic surface (ID extraction, summary formatting, error
paths in ``download_file``) without making any network calls.
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

# The skills package isn't on sys.path in normal pytest collection (it has no
# top-level __init__.py), so add it explicitly.
SKILLS_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(SKILLS_DIR))

import file_utils  # noqa: E402


def make_bash_tool_block(file_ids: list[str]):
    """Mimic the shape of a ``bash_code_execution_tool_result`` content block."""
    items = [SimpleNamespace(file_id=fid) for fid in file_ids]
    inner_content = SimpleNamespace(content=items)
    return SimpleNamespace(type="bash_code_execution_tool_result", content=inner_content)


def make_tool_result_block(output):
    return SimpleNamespace(type="tool_result", output=output)


class TestExtractFileIds:
    def test_empty_response(self):
        response = SimpleNamespace(content=[])
        assert file_utils.extract_file_ids(response) == []

    def test_single_bash_tool_block(self):
        response = SimpleNamespace(content=[make_bash_tool_block(["file_abc"])])
        assert file_utils.extract_file_ids(response) == ["file_abc"]

    def test_multiple_files_one_block(self):
        response = SimpleNamespace(content=[make_bash_tool_block(["file_a", "file_b", "file_c"])])
        assert file_utils.extract_file_ids(response) == ["file_a", "file_b", "file_c"]

    def test_dedupes_preserving_order(self):
        response = SimpleNamespace(
            content=[
                make_bash_tool_block(["file_a", "file_b"]),
                make_bash_tool_block(["file_a", "file_c"]),
            ]
        )
        assert file_utils.extract_file_ids(response) == ["file_a", "file_b", "file_c"]

    def test_legacy_tool_result_json_dict(self):
        response = SimpleNamespace(
            content=[make_tool_result_block(json.dumps({"file_id": "file_legacy"}))]
        )
        assert file_utils.extract_file_ids(response) == ["file_legacy"]

    def test_legacy_tool_result_json_list(self):
        payload = json.dumps([{"file_id": "f1"}, {"file_id": "f2"}, {"other": "x"}])
        response = SimpleNamespace(content=[make_tool_result_block(payload)])
        assert file_utils.extract_file_ids(response) == ["f1", "f2"]

    def test_legacy_tool_result_regex_fallback(self):
        # When output isn't JSON, fall back to regex.
        response = SimpleNamespace(
            content=[make_tool_result_block('Some text file_id="file_regex_123" more text')]
        )
        assert file_utils.extract_file_ids(response) == ["file_regex_123"]

    def test_other_block_types_ignored(self):
        text_block = SimpleNamespace(type="text", text="hello")
        response = SimpleNamespace(content=[text_block, make_bash_tool_block(["file_x"])])
        assert file_utils.extract_file_ids(response) == ["file_x"]


class TestDownloadFile:
    def test_creates_directory_and_writes_bytes(self, tmp_path: Path):
        client = MagicMock()
        client.beta.files.download.return_value = io.BytesIO(b"payload-data")

        out = tmp_path / "nested" / "out.bin"
        result = file_utils.download_file(client, "file_x", str(out))

        assert result["success"] is True
        assert result["size"] == len(b"payload-data")
        assert out.read_bytes() == b"payload-data"
        client.beta.files.download.assert_called_once_with(file_id="file_x")

    def test_respects_overwrite_false(self, tmp_path: Path):
        existing = tmp_path / "existing.bin"
        existing.write_bytes(b"old")
        client = MagicMock()

        result = file_utils.download_file(client, "fid", str(existing), overwrite=False)

        assert result["success"] is False
        assert "already exists" in result["error"]
        # The client must not be called when refusing to overwrite.
        client.beta.files.download.assert_not_called()
        # File should be untouched.
        assert existing.read_bytes() == b"old"

    def test_records_overwritten_flag(self, tmp_path: Path):
        existing = tmp_path / "existing.bin"
        existing.write_bytes(b"old")
        client = MagicMock()
        client.beta.files.download.return_value = io.BytesIO(b"new")

        result = file_utils.download_file(client, "fid", str(existing), overwrite=True)

        assert result["success"] is True
        assert result["overwritten"] is True
        assert existing.read_bytes() == b"new"

    def test_returns_error_on_exception(self, tmp_path: Path):
        client = MagicMock()
        client.beta.files.download.side_effect = RuntimeError("boom")
        result = file_utils.download_file(client, "fid", str(tmp_path / "out.bin"))
        assert result["success"] is False
        assert "boom" in result["error"]


class TestGetFileInfo:
    def test_maps_fields(self):
        client = MagicMock()
        client.beta.files.retrieve_metadata.return_value = SimpleNamespace(
            id="file_x",
            filename="report.xlsx",
            size_bytes=12345,
            mime_type="application/xlsx",
            created_at="2025-01-01T00:00:00Z",
            type="file",
            downloadable=True,
        )

        info = file_utils.get_file_info(client, "file_x")

        assert info == {
            "file_id": "file_x",
            "filename": "report.xlsx",
            "size": 12345,
            "mime_type": "application/xlsx",
            "created_at": "2025-01-01T00:00:00Z",
            "type": "file",
            "downloadable": True,
        }

    def test_returns_none_on_error(self, capsys):
        client = MagicMock()
        client.beta.files.retrieve_metadata.side_effect = RuntimeError("nope")
        assert file_utils.get_file_info(client, "f") is None


class TestDownloadAllFiles:
    def test_iterates_extracted_ids_with_metadata(self, tmp_path: Path):
        client = MagicMock()
        client.beta.files.retrieve_metadata.side_effect = [
            SimpleNamespace(filename="a.xlsx"),
            SimpleNamespace(filename="b.pptx"),
        ]
        client.beta.files.download.side_effect = [
            io.BytesIO(b"alpha"),
            io.BytesIO(b"beta"),
        ]

        response = SimpleNamespace(content=[make_bash_tool_block(["f1", "f2"])])

        results = file_utils.download_all_files(
            client, response, output_dir=str(tmp_path), prefix="run_"
        )

        assert len(results) == 2
        assert all(r["success"] for r in results)
        assert (tmp_path / "run_a.xlsx").read_bytes() == b"alpha"
        assert (tmp_path / "run_b.pptx").read_bytes() == b"beta"

    def test_falls_back_to_generic_filename_on_metadata_error(self, tmp_path: Path):
        client = MagicMock()
        client.beta.files.retrieve_metadata.side_effect = RuntimeError("metadata gone")
        client.beta.files.download.return_value = io.BytesIO(b"x")

        response = SimpleNamespace(content=[make_bash_tool_block(["only_id"])])
        results = file_utils.download_all_files(client, response, output_dir=str(tmp_path))

        assert results[0]["success"] is True
        assert results[0]["output_path"].endswith("file_1.bin")


class TestPrintDownloadSummary:
    def test_prints_success_and_failure(self, capsys):
        results = [
            {"output_path": "outputs/a.xlsx", "success": True, "size": 2048, "overwritten": False},
            {"output_path": "outputs/b.pdf", "success": False, "error": "boom"},
        ]
        file_utils.print_download_summary(results)
        out = capsys.readouterr().out
        assert "1/2 files downloaded successfully" in out
        assert "outputs/a.xlsx" in out
        assert "outputs/b.pdf" in out
        assert "boom" in out

    def test_marks_overwritten(self, capsys):
        results = [
            {"output_path": "outputs/a.xlsx", "success": True, "size": 100, "overwritten": True},
        ]
        file_utils.print_download_summary(results)
        out = capsys.readouterr().out
        assert "[overwritten]" in out


# Ensure module isolation: importing file_utils via this test file shouldn't
# leak into other suites that import the package differently.
def test_module_path():
    assert "skills" in str(Path(file_utils.__file__).parent)
