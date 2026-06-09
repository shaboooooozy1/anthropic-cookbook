"""Tests for ``skills/skill_utils.py`` — the Skills API helper surface.

``validate_skill_directory`` is pure filesystem logic and gets the most
coverage here. The API-backed helpers are exercised with a ``MagicMock`` client
(mirroring ``test_file_utils.py``) to assert the success/error dict shapes and
that exceptions are swallowed rather than raised.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

# The skills package isn't on sys.path in normal pytest collection.
SKILLS_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(SKILLS_DIR))

import skill_utils  # noqa: E402


def make_skill_dir(
    tmp_path: Path, frontmatter: str = "name: demo\ndescription: A demo skill"
) -> Path:
    """Create a minimal valid skill directory with a SKILL.md."""
    skill_dir = tmp_path / "demo"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(f"---\n{frontmatter}\n---\n\n# Demo\n", encoding="utf-8")
    return skill_dir


class TestValidateSkillDirectory:
    def test_valid_directory(self, tmp_path: Path):
        skill_dir = make_skill_dir(tmp_path)
        result = skill_utils.validate_skill_directory(str(skill_dir))
        assert result["valid"] is True
        assert result["errors"] == []
        assert result["info"]["file_count"] >= 1

    def test_missing_directory(self, tmp_path: Path):
        result = skill_utils.validate_skill_directory(str(tmp_path / "nope"))
        assert result["valid"] is False
        assert any("does not exist" in e for e in result["errors"])

    def test_missing_skill_md(self, tmp_path: Path):
        empty = tmp_path / "empty"
        empty.mkdir()
        result = skill_utils.validate_skill_directory(str(empty))
        assert result["valid"] is False
        assert any("SKILL.md" in e for e in result["errors"])

    def test_missing_frontmatter_delimiter(self, tmp_path: Path):
        skill_dir = tmp_path / "demo"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("name: demo\n", encoding="utf-8")
        result = skill_utils.validate_skill_directory(str(skill_dir))
        assert result["valid"] is False
        assert any("YAML frontmatter" in e for e in result["errors"])

    def test_missing_name_field(self, tmp_path: Path):
        skill_dir = make_skill_dir(tmp_path, frontmatter="description: only a description")
        result = skill_utils.validate_skill_directory(str(skill_dir))
        assert result["valid"] is False
        assert any("'name'" in e for e in result["errors"])

    def test_missing_description_field(self, tmp_path: Path):
        skill_dir = make_skill_dir(tmp_path, frontmatter="name: only-a-name")
        result = skill_utils.validate_skill_directory(str(skill_dir))
        assert result["valid"] is False
        assert any("'description'" in e for e in result["errors"])

    def test_unterminated_frontmatter(self, tmp_path: Path):
        skill_dir = tmp_path / "demo"
        skill_dir.mkdir()
        # Opens with --- but never closes it -> content.index("---", 3) raises.
        (skill_dir / "SKILL.md").write_text("---\nname: demo\n", encoding="utf-8")
        result = skill_utils.validate_skill_directory(str(skill_dir))
        assert result["valid"] is False
        assert any("Invalid YAML frontmatter" in e for e in result["errors"])

    def test_oversized_frontmatter(self, tmp_path: Path):
        big = "name: demo\ndescription: " + ("x" * 1100)
        skill_dir = make_skill_dir(tmp_path, frontmatter=big)
        result = skill_utils.validate_skill_directory(str(skill_dir))
        assert result["valid"] is False
        assert any("1024 chars" in e for e in result["errors"])

    def test_reports_reference_and_scripts(self, tmp_path: Path):
        skill_dir = make_skill_dir(tmp_path)
        (skill_dir / "REFERENCE.md").write_text("# ref", encoding="utf-8")
        scripts = skill_dir / "scripts"
        scripts.mkdir()
        (scripts / "run.py").write_text("print('hi')", encoding="utf-8")

        result = skill_utils.validate_skill_directory(str(skill_dir))
        assert result["info"]["has_reference"] is True
        assert result["info"]["has_scripts"] is True
        assert "run.py" in result["info"]["script_files"]


class TestCreateSkill:
    def test_missing_directory_returns_error(self, tmp_path: Path):
        result = skill_utils.create_skill(MagicMock(), str(tmp_path / "nope"), "Demo")
        assert result["success"] is False
        assert "does not exist" in result["error"]

    def test_missing_skill_md_returns_error(self, tmp_path: Path):
        empty = tmp_path / "empty"
        empty.mkdir()
        result = skill_utils.create_skill(MagicMock(), str(empty), "Demo")
        assert result["success"] is False
        assert "SKILL.md not found" in result["error"]

    def test_success_shape(self, tmp_path: Path, monkeypatch):
        skill_dir = make_skill_dir(tmp_path)
        # files_from_dir touches the filesystem/SDK; stub it out.
        monkeypatch.setattr(skill_utils, "files_from_dir", lambda p: [])

        client = MagicMock()
        client.beta.skills.create.return_value = SimpleNamespace(
            id="skill_123",
            display_title="Demo",
            latest_version="0.0.1",
            created_at="2025-01-01T00:00:00Z",
            source="custom",
        )

        result = skill_utils.create_skill(client, str(skill_dir), "Demo")
        assert result["success"] is True
        assert result["skill_id"] == "skill_123"
        assert result["source"] == "custom"

    def test_swallows_api_exception(self, tmp_path: Path, monkeypatch):
        skill_dir = make_skill_dir(tmp_path)
        monkeypatch.setattr(skill_utils, "files_from_dir", lambda p: [])
        client = MagicMock()
        client.beta.skills.create.side_effect = RuntimeError("boom")

        result = skill_utils.create_skill(client, str(skill_dir), "Demo")
        assert result["success"] is False
        assert "boom" in result["error"]


class TestListAndVersions:
    def test_list_custom_skills_maps_fields(self):
        client = MagicMock()
        client.beta.skills.list.return_value = SimpleNamespace(
            data=[
                SimpleNamespace(
                    id="s1",
                    display_title="One",
                    latest_version="1",
                    created_at="t",
                    updated_at="t2",
                )
            ]
        )
        skills = skill_utils.list_custom_skills(client)
        assert skills == [
            {
                "skill_id": "s1",
                "display_title": "One",
                "latest_version": "1",
                "created_at": "t",
                "updated_at": "t2",
            }
        ]

    def test_list_custom_skills_returns_empty_on_error(self, capsys):
        client = MagicMock()
        client.beta.skills.list.side_effect = RuntimeError("nope")
        assert skill_utils.list_custom_skills(client) == []
        assert "Error listing skills" in capsys.readouterr().out

    def test_get_skill_version_resolves_latest(self):
        client = MagicMock()
        client.beta.skills.retrieve.return_value = SimpleNamespace(latest_version="3")
        client.beta.skills.versions.retrieve.return_value = SimpleNamespace(
            version="3",
            skill_id="s1",
            name="demo",
            description="d",
            directory="/d",
            created_at="t",
        )
        info = skill_utils.get_skill_version(client, "s1")
        assert info["version"] == "3"
        client.beta.skills.versions.retrieve.assert_called_once_with(skill_id="s1", version="3")

    def test_get_skill_version_returns_none_on_error(self, capsys):
        client = MagicMock()
        client.beta.skills.retrieve.side_effect = RuntimeError("x")
        assert skill_utils.get_skill_version(client, "s1") is None

    def test_list_skill_versions_returns_empty_on_error(self):
        client = MagicMock()
        client.beta.skills.versions.list.side_effect = RuntimeError("x")
        assert skill_utils.list_skill_versions(client, "s1") == []


class TestDeleteSkill:
    def test_deletes_versions_then_skill(self):
        client = MagicMock()
        client.beta.skills.versions.list.return_value = SimpleNamespace(
            data=[SimpleNamespace(version="1"), SimpleNamespace(version="2")]
        )
        assert skill_utils.delete_skill(client, "s1", delete_versions=True) is True
        assert client.beta.skills.versions.delete.call_count == 2
        client.beta.skills.delete.assert_called_once_with("s1")

    def test_skips_version_deletion_when_disabled(self):
        client = MagicMock()
        assert skill_utils.delete_skill(client, "s1", delete_versions=False) is True
        client.beta.skills.versions.list.assert_not_called()
        client.beta.skills.delete.assert_called_once_with("s1")

    def test_returns_false_on_error(self, capsys):
        client = MagicMock()
        client.beta.skills.delete.side_effect = RuntimeError("boom")
        assert skill_utils.delete_skill(client, "s1", delete_versions=False) is False
        assert "Error deleting skill" in capsys.readouterr().out


class TestTestSkill:
    def test_builds_request_with_default_model_and_betas(self):
        client = MagicMock()
        client.beta.messages.create.return_value = SimpleNamespace(id="msg")

        skill_utils.test_skill(client, "s1", "do a thing")

        _, kwargs = client.beta.messages.create.call_args
        # Guards against silent model drift in the example helper.
        assert kwargs["model"] == "claude-sonnet-4-6"
        assert "skills-2025-10-02" in kwargs["betas"]
        assert kwargs["container"]["skills"] == [
            {"type": "custom", "skill_id": "s1", "version": "latest"}
        ]

    def test_includes_anthropic_skills(self):
        client = MagicMock()
        client.beta.messages.create.return_value = SimpleNamespace(id="msg")

        skill_utils.test_skill(client, "s1", "go", include_anthropic_skills=["xlsx", "pptx"])

        _, kwargs = client.beta.messages.create.call_args
        skills = kwargs["container"]["skills"]
        assert {"type": "anthropic", "skill_id": "xlsx", "version": "latest"} in skills
        assert {"type": "anthropic", "skill_id": "pptx", "version": "latest"} in skills


class TestPrintSkillSummary:
    def test_prints_fields(self, capsys):
        skill_utils.print_skill_summary(
            {
                "display_title": "Demo",
                "skill_id": "s1",
                "latest_version": "1",
                "source": "custom",
                "created_at": "t",
            }
        )
        out = capsys.readouterr().out
        assert "Demo" in out
        assert "s1" in out

    def test_prints_error_when_present(self, capsys):
        skill_utils.print_skill_summary({"error": "something failed"})
        assert "something failed" in capsys.readouterr().out
