from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest

from skills import skill_utils


def test_validate_skill_directory_missing_directory(tmp_path: Path):
    result = skill_utils.validate_skill_directory(str(tmp_path / "missing"))
    assert result["valid"] is False
    assert "does not exist" in result["errors"][0]


def test_validate_skill_directory_requires_skill_md(tmp_path: Path):
    skill_dir = tmp_path / "skill"
    skill_dir.mkdir()
    result = skill_utils.validate_skill_directory(str(skill_dir))
    assert result["valid"] is False
    assert "SKILL.md file is required" in result["errors"]


def test_validate_skill_directory_frontmatter_required(tmp_path: Path):
    skill_dir = tmp_path / "skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("no frontmatter", encoding="utf-8")
    result = skill_utils.validate_skill_directory(str(skill_dir))
    assert result["valid"] is False
    assert any("frontmatter" in e.lower() for e in result["errors"])


def test_validate_skill_directory_missing_required_fields(tmp_path: Path):
    skill_dir = tmp_path / "skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("---\ndescription: x\n---\n", encoding="utf-8")
    result = skill_utils.validate_skill_directory(str(skill_dir))
    assert result["valid"] is False
    assert any("'name'" in e for e in result["errors"])


def test_validate_skill_directory_invalid_frontmatter_format(tmp_path: Path):
    skill_dir = tmp_path / "skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("---\nname: x\ndescription: y\n", encoding="utf-8")
    result = skill_utils.validate_skill_directory(str(skill_dir))
    assert result["valid"] is False
    assert any("invalid yaml frontmatter format" in e.lower() for e in result["errors"])


def test_validate_skill_directory_detects_reference_and_scripts(tmp_path: Path):
    skill_dir = tmp_path / "skill"
    (skill_dir / "scripts").mkdir(parents=True)
    (skill_dir / "scripts" / "a.py").write_text("print(1)\n", encoding="utf-8")
    (skill_dir / "REFERENCE.md").write_text("ref", encoding="utf-8")
    (skill_dir / "SKILL.md").write_text("---\nname: x\ndescription: y\n---\n", encoding="utf-8")

    result = skill_utils.validate_skill_directory(str(skill_dir))
    assert result["valid"] is True
    assert result["info"]["has_reference"] is True
    assert result["info"]["has_scripts"] is True
    assert result["info"]["script_files"] == ["a.py"]


def test_print_skill_summary_includes_error(capsys: pytest.CaptureFixture[str]):
    skill_utils.print_skill_summary({"display_title": "T", "skill_id": "s", "error": "bad"})
    out = capsys.readouterr().out
    assert "Skill: T" in out
    assert "Error: bad" in out


def test_create_skill_validates_directory_and_skill_md(tmp_path: Path):
    client = _FakeClient()
    missing = skill_utils.create_skill(client, str(tmp_path / "missing"), "Demo")
    assert missing["success"] is False
    assert "does not exist" in missing["error"]

    skill_dir = tmp_path / "skill"
    skill_dir.mkdir()
    no_skill_md = skill_utils.create_skill(client, str(skill_dir), "Demo")
    assert no_skill_md["success"] is False
    assert "SKILL.md not found" in no_skill_md["error"]


def test_list_custom_skills_returns_empty_on_exception(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
):
    client = _FakeClient()

    def boom(*_args, **_kwargs):  # noqa: ANN001
        raise RuntimeError("nope")

    monkeypatch.setattr(client.beta.skills, "list", boom)
    assert skill_utils.list_custom_skills(client) == []
    assert "Error listing skills" in capsys.readouterr().out


@dataclass
class _FakeVersion:
    version: str
    skill_id: str
    created_at: str = "now"


@dataclass
class _FakeSkill:
    id: str
    display_title: str = "Title"
    latest_version: str = "v1"
    created_at: str = "now"
    updated_at: str = "later"
    source: str = "custom"


class _FakeClient:
    def __init__(self):
        self.calls = []
        self.beta = SimpleNamespace(
            skills=SimpleNamespace(
                create=self._create,
                list=self._list,
                retrieve=self._retrieve,
                delete=self._delete_skill,
                versions=SimpleNamespace(
                    create=self._create_version,
                    list=self._list_versions,
                    retrieve=self._retrieve_version,
                    delete=self._delete_version,
                ),
            ),
            messages=SimpleNamespace(create=self._create_message),
        )

    def _create(self, display_title, files):  # noqa: ANN001
        self.calls.append(("skills.create", display_title, files))
        return _FakeSkill(id="skill_1", display_title=display_title)

    def _list(self, source):  # noqa: ANN001
        self.calls.append(("skills.list", source))
        return SimpleNamespace(data=[_FakeSkill(id="skill_1"), _FakeSkill(id="skill_2")])

    def _retrieve(self, skill_id):  # noqa: ANN001
        self.calls.append(("skills.retrieve", skill_id))
        return _FakeSkill(id=skill_id, latest_version="v2")

    def _delete_skill(self, skill_id):  # noqa: ANN001
        self.calls.append(("skills.delete", skill_id))

    def _create_version(self, skill_id, files):  # noqa: ANN001
        self.calls.append(("versions.create", skill_id, files))
        return _FakeVersion(version="v2", skill_id=skill_id)

    def _list_versions(self, skill_id):  # noqa: ANN001
        self.calls.append(("versions.list", skill_id))
        return SimpleNamespace(data=[_FakeVersion("v1", skill_id), _FakeVersion("v2", skill_id)])

    def _retrieve_version(self, skill_id, version):  # noqa: ANN001
        self.calls.append(("versions.retrieve", skill_id, version))
        return SimpleNamespace(
            version=version,
            skill_id=skill_id,
            name="n",
            description="d",
            directory="/",
            created_at="now",
        )

    def _delete_version(self, skill_id, version):  # noqa: ANN001
        self.calls.append(("versions.delete", skill_id, version))

    def _create_message(self, **kwargs):  # noqa: ANN003
        self.calls.append(("messages.create", kwargs))
        return {"ok": True}


def test_client_wrappers_smoke(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    client = _FakeClient()

    # Create skill validates SKILL.md presence.
    skill_dir = tmp_path / "skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("---\nname: x\ndescription: y\n---\n", encoding="utf-8")

    monkeypatch.setattr(skill_utils, "files_from_dir", lambda _p: ["file"])
    created = skill_utils.create_skill(client, str(skill_dir), "Demo")
    assert created["success"] is True
    assert created["skill_id"] == "skill_1"

    skills = skill_utils.list_custom_skills(client)
    assert [s["skill_id"] for s in skills] == ["skill_1", "skill_2"]

    version = skill_utils.get_skill_version(client, "skill_1")
    assert version is not None
    assert version["version"] == "v2"

    created_version = skill_utils.create_skill_version(client, "skill_1", str(skill_dir))
    assert created_version["success"] is True
    assert created_version["version"] == "v2"

    versions = skill_utils.list_skill_versions(client, "skill_1")
    assert [v["version"] for v in versions] == ["v1", "v2"]

    assert skill_utils.delete_skill(client, "skill_1", delete_versions=True) is True

    resp = skill_utils.test_skill(
        client,
        "skill_1",
        "hi",
        include_anthropic_skills=["xlsx"],
    )
    assert resp == {"ok": True}
