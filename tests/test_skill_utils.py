"""Tests for skills/skill_utils.py.

These tests validate the skill management utilities without making actual API calls.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

# Add skills directory to path to import the module
SKILLS_DIR = Path(__file__).parent.parent / "skills"
sys.path.insert(0, str(SKILLS_DIR))

import skill_utils  # noqa: E402


class TestCreateSkill:
    """Tests for create_skill function."""

    def test_missing_directory(self):
        """Test handling of non-existent skill directory."""
        client = MagicMock()
        result = skill_utils.create_skill(client, "/nonexistent/path", "Test Skill")

        assert result["success"] is False
        assert "does not exist" in result["error"]
        client.beta.skills.create.assert_not_called()

    def test_missing_skill_md(self, tmp_path: Path):
        """Test handling of missing SKILL.md file."""
        skill_dir = tmp_path / "skill"
        skill_dir.mkdir()

        client = MagicMock()
        result = skill_utils.create_skill(client, str(skill_dir), "Test Skill")

        assert result["success"] is False
        assert "SKILL.md not found" in result["error"]

    def test_successful_creation(self, tmp_path: Path):
        """Test successful skill creation."""
        skill_dir = tmp_path / "skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("---\nname: test\n---\n# Test")

        client = MagicMock()
        client.beta.skills.create.return_value = SimpleNamespace(
            id="skill_123",
            display_title="Test Skill",
            latest_version="v1",
            created_at="2025-01-01",
            source="custom",
        )

        result = skill_utils.create_skill(client, str(skill_dir), "Test Skill")

        assert result["success"] is True
        assert result["skill_id"] == "skill_123"
        assert result["display_title"] == "Test Skill"
        assert result["latest_version"] == "v1"
        assert result["source"] == "custom"
        client.beta.skills.create.assert_called_once()

    def test_api_exception(self, tmp_path: Path):
        """Test handling of API exceptions."""
        skill_dir = tmp_path / "skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("content")

        client = MagicMock()
        client.beta.skills.create.side_effect = RuntimeError("API error")

        result = skill_utils.create_skill(client, str(skill_dir), "Test")

        assert result["success"] is False
        assert "API error" in result["error"]


class TestListCustomSkills:
    """Tests for list_custom_skills function."""

    def test_returns_skills_list(self):
        """Test successful listing of custom skills."""
        client = MagicMock()
        client.beta.skills.list.return_value = SimpleNamespace(
            data=[
                SimpleNamespace(
                    id="skill_1",
                    display_title="Skill 1",
                    latest_version="v1",
                    created_at="2025-01-01",
                    updated_at="2025-01-02",
                ),
                SimpleNamespace(
                    id="skill_2",
                    display_title="Skill 2",
                    latest_version="v2",
                    created_at="2025-01-03",
                    updated_at="2025-01-04",
                ),
            ]
        )

        skills = skill_utils.list_custom_skills(client)

        assert len(skills) == 2
        assert skills[0]["skill_id"] == "skill_1"
        assert skills[1]["display_title"] == "Skill 2"
        client.beta.skills.list.assert_called_once_with(source="custom")

    def test_handles_exception(self, capsys):
        """Test exception handling in list_custom_skills."""
        client = MagicMock()
        client.beta.skills.list.side_effect = RuntimeError("List error")

        skills = skill_utils.list_custom_skills(client)

        assert skills == []
        captured = capsys.readouterr()
        assert "Error listing skills" in captured.out


class TestGetSkillVersion:
    """Tests for get_skill_version function."""

    def test_get_latest_version(self):
        """Test retrieving latest version."""
        client = MagicMock()
        client.beta.skills.retrieve.return_value = SimpleNamespace(latest_version="v3")
        client.beta.skills.versions.retrieve.return_value = SimpleNamespace(
            version="v3",
            skill_id="skill_123",
            name="test",
            description="desc",
            directory="/dir",
            created_at="2025-01-01",
        )

        info = skill_utils.get_skill_version(client, "skill_123")

        assert info["version"] == "v3"
        assert info["skill_id"] == "skill_123"
        client.beta.skills.retrieve.assert_called_once_with("skill_123")

    def test_get_specific_version(self):
        """Test retrieving specific version."""
        client = MagicMock()
        client.beta.skills.versions.retrieve.return_value = SimpleNamespace(
            version="v1",
            skill_id="skill_123",
            name="test",
            description="desc",
            directory="/dir",
            created_at="2025-01-01",
        )

        info = skill_utils.get_skill_version(client, "skill_123", version="v1")

        assert info["version"] == "v1"
        # Should not call retrieve when version is specified
        client.beta.skills.retrieve.assert_not_called()

    def test_handles_exception(self, capsys):
        """Test exception handling."""
        client = MagicMock()
        client.beta.skills.retrieve.side_effect = RuntimeError("Not found")

        info = skill_utils.get_skill_version(client, "skill_123")

        assert info is None
        captured = capsys.readouterr()
        assert "Error getting skill version" in captured.out


class TestCreateSkillVersion:
    """Tests for create_skill_version function."""

    def test_successful_version_creation(self, tmp_path: Path):
        """Test successful creation of new skill version."""
        skill_dir = tmp_path / "skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("content")

        client = MagicMock()
        client.beta.skills.versions.create.return_value = SimpleNamespace(
            version="v2", skill_id="skill_123", created_at="2025-01-01"
        )

        result = skill_utils.create_skill_version(client, "skill_123", str(skill_dir))

        assert result["success"] is True
        assert result["version"] == "v2"
        assert result["skill_id"] == "skill_123"

    def test_handles_exception(self, tmp_path: Path):
        """Test exception handling in version creation."""
        skill_dir = tmp_path / "skill"
        skill_dir.mkdir()

        client = MagicMock()
        client.beta.skills.versions.create.side_effect = RuntimeError("Version error")

        result = skill_utils.create_skill_version(client, "skill_123", str(skill_dir))

        assert result["success"] is False
        assert "Version error" in result["error"]


class TestDeleteSkill:
    """Tests for delete_skill function."""

    def test_delete_with_versions(self, capsys):
        """Test deleting skill and its versions."""
        client = MagicMock()
        client.beta.skills.versions.list.return_value = SimpleNamespace(
            data=[
                SimpleNamespace(version="v1"),
                SimpleNamespace(version="v2"),
            ]
        )

        success = skill_utils.delete_skill(client, "skill_123", delete_versions=True)

        assert success is True
        assert client.beta.skills.versions.delete.call_count == 2
        client.beta.skills.delete.assert_called_once_with("skill_123")

    def test_delete_without_versions(self):
        """Test deleting skill without deleting versions first."""
        client = MagicMock()

        success = skill_utils.delete_skill(client, "skill_123", delete_versions=False)

        assert success is True
        client.beta.skills.versions.list.assert_not_called()
        client.beta.skills.delete.assert_called_once()

    def test_handles_exception(self, capsys):
        """Test exception handling in delete."""
        client = MagicMock()
        client.beta.skills.versions.list.side_effect = RuntimeError("Delete error")

        success = skill_utils.delete_skill(client, "skill_123")

        assert success is False
        captured = capsys.readouterr()
        assert "Error deleting skill" in captured.out


class TestTestSkill:
    """Tests for test_skill function."""

    def test_creates_message_with_skill(self):
        """Test that test_skill creates proper message."""
        client = MagicMock()
        client.beta.messages.create.return_value = SimpleNamespace(content=[])

        skill_utils.test_skill(client, "skill_123", "test prompt")

        client.beta.messages.create.assert_called_once()
        call_kwargs = client.beta.messages.create.call_args[1]
        assert call_kwargs["model"] == "claude-sonnet-4-6"
        assert len(call_kwargs["messages"]) == 1
        assert call_kwargs["messages"][0]["content"] == "test prompt"

    def test_includes_anthropic_skills(self):
        """Test including Anthropic skills."""
        client = MagicMock()
        client.beta.messages.create.return_value = SimpleNamespace(content=[])

        skill_utils.test_skill(
            client, "skill_123", "prompt", include_anthropic_skills=["xlsx", "pdf"]
        )

        call_kwargs = client.beta.messages.create.call_args[1]
        skills = call_kwargs["container"]["skills"]
        assert len(skills) == 3  # 1 custom + 2 anthropic
        assert skills[0]["type"] == "custom"
        assert skills[1]["type"] == "anthropic"
        assert skills[2]["type"] == "anthropic"


class TestListSkillVersions:
    """Tests for list_skill_versions function."""

    def test_lists_versions(self):
        """Test successful listing of versions."""
        client = MagicMock()
        client.beta.skills.versions.list.return_value = SimpleNamespace(
            data=[
                SimpleNamespace(version="v1", skill_id="skill_123", created_at="2025-01-01"),
                SimpleNamespace(version="v2", skill_id="skill_123", created_at="2025-01-02"),
            ]
        )

        versions = skill_utils.list_skill_versions(client, "skill_123")

        assert len(versions) == 2
        assert versions[0]["version"] == "v1"
        assert versions[1]["version"] == "v2"

    def test_handles_exception(self, capsys):
        """Test exception handling."""
        client = MagicMock()
        client.beta.skills.versions.list.side_effect = RuntimeError("List error")

        versions = skill_utils.list_skill_versions(client, "skill_123")

        assert versions == []
        captured = capsys.readouterr()
        assert "Error listing versions" in captured.out


class TestValidateSkillDirectory:
    """Tests for validate_skill_directory function."""

    def test_nonexistent_directory(self):
        """Test validation of non-existent directory."""
        result = skill_utils.validate_skill_directory("/nonexistent")

        assert result["valid"] is False
        assert any("does not exist" in e for e in result["errors"])

    def test_missing_skill_md(self, tmp_path: Path):
        """Test validation when SKILL.md is missing."""
        skill_dir = tmp_path / "skill"
        skill_dir.mkdir()

        result = skill_utils.validate_skill_directory(str(skill_dir))

        assert result["valid"] is False
        assert any("SKILL.md" in e and "required" in e for e in result["errors"])

    def test_invalid_frontmatter(self, tmp_path: Path):
        """Test validation of invalid YAML frontmatter."""
        skill_dir = tmp_path / "skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("# No frontmatter")

        result = skill_utils.validate_skill_directory(str(skill_dir))

        assert result["valid"] is False
        assert any("frontmatter" in e for e in result["errors"])

    def test_missing_required_fields(self, tmp_path: Path):
        """Test validation when required fields are missing."""
        skill_dir = tmp_path / "skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("---\nother: value\n---\n")

        result = skill_utils.validate_skill_directory(str(skill_dir))

        assert result["valid"] is False
        assert any("name" in e for e in result["errors"])
        assert any("description" in e for e in result["errors"])

    def test_valid_skill_directory(self, tmp_path: Path):
        """Test validation of a valid skill directory."""
        skill_dir = tmp_path / "skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\nname: test-skill\ndescription: A test skill\n---\n# Content"
        )

        result = skill_utils.validate_skill_directory(str(skill_dir))

        assert result["valid"] is True
        assert result["errors"] == []
        assert "total_size_mb" in result["info"]
        assert "file_count" in result["info"]

    def test_detects_optional_files(self, tmp_path: Path):
        """Test detection of optional REFERENCE.md and scripts."""
        skill_dir = tmp_path / "skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\nname: test\ndescription: test\n---\ncontent"
        )
        (skill_dir / "REFERENCE.md").write_text("Reference docs")
        scripts_dir = skill_dir / "scripts"
        scripts_dir.mkdir()
        (scripts_dir / "helper.py").write_text("# helper")

        result = skill_utils.validate_skill_directory(str(skill_dir))

        assert result["valid"] is True
        assert result["info"]["has_reference"] is True
        assert result["info"]["has_scripts"] is True
        assert "helper.py" in result["info"]["script_files"]

    def test_size_limit(self, tmp_path: Path):
        """Test validation of file size limits."""
        skill_dir = tmp_path / "skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\nname: test\ndescription: test\n---\ncontent"
        )
        # Create a large file (> 8MB)
        large_file = skill_dir / "large.bin"
        large_file.write_bytes(b"x" * (9 * 1024 * 1024))  # 9 MB

        result = skill_utils.validate_skill_directory(str(skill_dir))

        assert result["valid"] is False
        assert any("exceeds 8MB" in e for e in result["errors"])

    def test_frontmatter_size_limit(self, tmp_path: Path):
        """Test validation of frontmatter size limit."""
        skill_dir = tmp_path / "skill"
        skill_dir.mkdir()
        large_description = "x" * 2000
        (skill_dir / "SKILL.md").write_text(
            f"---\nname: test\ndescription: {large_description}\n---\ncontent"
        )

        result = skill_utils.validate_skill_directory(str(skill_dir))

        assert result["valid"] is False
        assert any("frontmatter exceeds" in e for e in result["errors"])


class TestPrintSkillSummary:
    """Tests for print_skill_summary function."""

    def test_prints_summary(self, capsys):
        """Test printing of skill summary."""
        skill_info = {
            "display_title": "Test Skill",
            "skill_id": "skill_123",
            "latest_version": "v1",
            "source": "custom",
            "created_at": "2025-01-01",
        }

        skill_utils.print_skill_summary(skill_info)

        captured = capsys.readouterr()
        assert "Test Skill" in captured.out
        assert "skill_123" in captured.out
        assert "v1" in captured.out

    def test_prints_error(self, capsys):
        """Test printing of error in summary."""
        skill_info = {"error": "Something went wrong"}

        skill_utils.print_skill_summary(skill_info)

        captured = capsys.readouterr()
        assert "Error" in captured.out
        assert "Something went wrong" in captured.out
