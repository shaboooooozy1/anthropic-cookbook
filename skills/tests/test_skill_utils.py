"""Tests for ``skills/skill_utils.py`` — Skills API helpers used by the Skills notebooks.

These tests use mocks + temporary directories to avoid any network calls.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

# The skills package isn't on sys.path in normal pytest collection (it has no
# top-level __init__.py), so add it explicitly.
SKILLS_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(SKILLS_DIR))

import skill_utils  # noqa: E402


class TestCreateSkill:
    def test_returns_error_if_directory_missing(self):
        client = MagicMock()
        result = skill_utils.create_skill(client, "does-not-exist", "Title")
        assert result["success"] is False
        assert "does not exist" in result["error"]

    def test_returns_error_if_skill_md_missing(self, tmp_path: Path):
        client = MagicMock()
        result = skill_utils.create_skill(client, str(tmp_path), "Title")
        assert result["success"] is False
        assert "SKILL.md not found" in result["error"]

    def test_calls_api_when_valid_directory(self, tmp_path: Path):
        (tmp_path / "SKILL.md").write_text("---\nname: x\ndescription: y\n---\n", encoding="utf-8")

        client = MagicMock()
        client.beta.skills.create.return_value = SimpleNamespace(
            id="skill_123",
            display_title="My Skill",
            latest_version="v1",
            created_at="2026-01-01T00:00:00Z",
            source="custom",
        )

        result = skill_utils.create_skill(client, str(tmp_path), "My Skill")

        assert result["success"] is True
        assert result["skill_id"] == "skill_123"
        client.beta.skills.create.assert_called_once()

    def test_returns_error_on_api_exception(self, tmp_path: Path):
        (tmp_path / "SKILL.md").write_text("---\nname: x\ndescription: y\n---\n", encoding="utf-8")
        client = MagicMock()
        client.beta.skills.create.side_effect = RuntimeError("boom")

        result = skill_utils.create_skill(client, str(tmp_path), "My Skill")
        assert result["success"] is False
        assert "boom" in result["error"]


class TestListCustomSkills:
    def test_maps_response_objects(self):
        client = MagicMock()
        client.beta.skills.list.return_value = SimpleNamespace(
            data=[
                SimpleNamespace(
                    id="s1",
                    display_title="A",
                    latest_version="1",
                    created_at="c",
                    updated_at="u",
                )
            ]
        )
        skills = skill_utils.list_custom_skills(client)
        assert skills == [
            {
                "skill_id": "s1",
                "display_title": "A",
                "latest_version": "1",
                "created_at": "c",
                "updated_at": "u",
            }
        ]

    def test_returns_empty_list_on_error(self):
        client = MagicMock()
        client.beta.skills.list.side_effect = RuntimeError("boom")
        assert skill_utils.list_custom_skills(client) == []


class TestGetSkillVersion:
    def test_latest_expands_to_concrete_version(self):
        client = MagicMock()
        client.beta.skills.retrieve.return_value = SimpleNamespace(latest_version="v9")
        client.beta.skills.versions.retrieve.return_value = SimpleNamespace(
            version="v9",
            skill_id="skill_abc",
            name="n",
            description="d",
            directory="dir",
            created_at="t",
        )
        info = skill_utils.get_skill_version(client, "skill_abc", version="latest")
        assert info["version"] == "v9"
        client.beta.skills.retrieve.assert_called_once_with("skill_abc")
        client.beta.skills.versions.retrieve.assert_called_once_with(
            skill_id="skill_abc", version="v9"
        )

    def test_returns_none_on_error(self):
        client = MagicMock()
        client.beta.skills.versions.retrieve.side_effect = RuntimeError("nope")
        assert skill_utils.get_skill_version(client, "skill_abc", version="v1") is None


class TestCreateSkillVersion:
    def test_success(self, tmp_path: Path):
        client = MagicMock()
        client.beta.skills.versions.create.return_value = SimpleNamespace(
            version="v2", skill_id="skill_abc", created_at="now"
        )
        result = skill_utils.create_skill_version(client, "skill_abc", str(tmp_path))
        assert result["success"] is True
        assert result["version"] == "v2"

    def test_error(self, tmp_path: Path):
        client = MagicMock()
        client.beta.skills.versions.create.side_effect = RuntimeError("boom")
        result = skill_utils.create_skill_version(client, "skill_abc", str(tmp_path))
        assert result["success"] is False
        assert "boom" in result["error"]


class TestDeleteSkill:
    def test_deletes_versions_then_skill(self, capsys):
        client = MagicMock()
        client.beta.skills.versions.list.return_value = SimpleNamespace(
            data=[SimpleNamespace(version="v1"), SimpleNamespace(version="v2")]
        )

        assert skill_utils.delete_skill(client, "skill_abc", delete_versions=True) is True
        client.beta.skills.versions.delete.assert_any_call(skill_id="skill_abc", version="v1")
        client.beta.skills.versions.delete.assert_any_call(skill_id="skill_abc", version="v2")
        client.beta.skills.delete.assert_called_once_with("skill_abc")

        out = capsys.readouterr().out
        assert "Deleted version" in out
        assert "Deleted skill" in out

    def test_returns_false_on_error(self):
        client = MagicMock()
        client.beta.skills.delete.side_effect = RuntimeError("boom")
        assert skill_utils.delete_skill(client, "skill_abc", delete_versions=False) is False


class TestTestSkill:
    def test_builds_skills_container(self):
        client = MagicMock()
        client.beta.messages.create.return_value = SimpleNamespace(id="msg_1")

        resp = skill_utils.test_skill(
            client,
            "skill_abc",
            "hello",
            include_anthropic_skills=["xlsx"],
        )

        assert resp.id == "msg_1"
        _kwargs = client.beta.messages.create.call_args.kwargs
        assert _kwargs["container"]["skills"][0]["type"] == "custom"
        assert any(
            s["type"] == "anthropic" and s["skill_id"] == "xlsx"
            for s in _kwargs["container"]["skills"]
        )


class TestListSkillVersions:
    def test_maps_versions(self):
        client = MagicMock()
        client.beta.skills.versions.list.return_value = SimpleNamespace(
            data=[SimpleNamespace(version="v1", skill_id="s", created_at="t")]
        )
        versions = skill_utils.list_skill_versions(client, "s")
        assert versions == [{"version": "v1", "skill_id": "s", "created_at": "t"}]

    def test_returns_empty_list_on_error(self):
        client = MagicMock()
        client.beta.skills.versions.list.side_effect = RuntimeError("boom")
        assert skill_utils.list_skill_versions(client, "s") == []


class TestValidateSkillDirectory:
    def test_missing_directory(self):
        result = skill_utils.validate_skill_directory("nope")
        assert result["valid"] is False
        assert result["errors"]

    def test_requires_skill_md(self, tmp_path: Path):
        result = skill_utils.validate_skill_directory(str(tmp_path))
        assert result["valid"] is False
        assert "SKILL.md file is required" in result["errors"]

    def test_validates_frontmatter_and_counts_files(self, tmp_path: Path):
        (tmp_path / "SKILL.md").write_text(
            "---\nname: demo\ndescription: test\n---\nBody\n", encoding="utf-8"
        )
        (tmp_path / "REFERENCE.md").write_text("ref", encoding="utf-8")
        scripts = tmp_path / "scripts"
        scripts.mkdir()
        (scripts / "a.py").write_text("print('x')", encoding="utf-8")

        result = skill_utils.validate_skill_directory(str(tmp_path))
        assert result["valid"] is True
        assert result["info"]["has_reference"] is True
        assert result["info"]["has_scripts"] is True
        assert "a.py" in result["info"]["script_files"]

    def test_rejects_missing_frontmatter(self, tmp_path: Path):
        (tmp_path / "SKILL.md").write_text("no frontmatter", encoding="utf-8")
        result = skill_utils.validate_skill_directory(str(tmp_path))
        assert result["valid"] is False
        assert any("frontmatter" in e for e in result["errors"])

    def test_missing_required_fields_are_reported(self, tmp_path: Path):
        (tmp_path / "SKILL.md").write_text("---\n# no required fields\n---\n", encoding="utf-8")
        result = skill_utils.validate_skill_directory(str(tmp_path))
        assert result["valid"] is False
        assert any("'name' field" in e for e in result["errors"])
        assert any("'description' field" in e for e in result["errors"])

    def test_invalid_frontmatter_delimiters_are_reported(self, tmp_path: Path):
        (tmp_path / "SKILL.md").write_text("---\nname: x\ndescription: y\n", encoding="utf-8")
        result = skill_utils.validate_skill_directory(str(tmp_path))
        assert result["valid"] is False
        assert any("Invalid YAML frontmatter format" in e for e in result["errors"])

    def test_total_size_limit_enforced(self, tmp_path: Path):
        (tmp_path / "SKILL.md").write_text(
            "---\nname: demo\ndescription: test\n---\n", encoding="utf-8"
        )
        big = tmp_path / "big.bin"
        with open(big, "wb") as f:
            f.seek(8 * 1024 * 1024)
            f.write(b"x")

        result = skill_utils.validate_skill_directory(str(tmp_path))
        assert result["valid"] is False
        assert any("exceeds 8MB" in e for e in result["errors"])

    def test_frontmatter_size_limit_enforced(self, tmp_path: Path):
        huge = "a" * 1100
        (tmp_path / "SKILL.md").write_text(
            f"---\nname: demo\ndescription: {huge}\n---\n", encoding="utf-8"
        )
        result = skill_utils.validate_skill_directory(str(tmp_path))
        assert result["valid"] is False
        assert any("exceeds 1024 chars" in e for e in result["errors"])


class TestPrintSkillSummary:
    def test_prints_error_field(self, capsys):
        skill_utils.print_skill_summary(
            {"display_title": "X", "skill_id": "s", "latest_version": "v", "error": "boom"}
        )
        out = capsys.readouterr().out
        assert "Skill: X" in out
        assert "Error: boom" in out
