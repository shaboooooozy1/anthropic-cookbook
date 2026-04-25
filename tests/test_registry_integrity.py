"""Offline integrity tests for registry.yaml ↔ authors.yaml ↔ filesystem.

The existing .github/scripts/verify_registry.py does similar checks but
requires network (it pings GitHub for every author). These tests run on
every PR with no network needed, catching the most common regression:
adding a notebook without registering it, registering a path that doesn't
exist, or referencing an author that hasn't been defined.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = REPO_ROOT / "registry.yaml"
AUTHORS_PATH = REPO_ROOT / "authors.yaml"

# Notebooks that intentionally live outside registry.yaml (e.g. supplementary
# material referenced by another notebook). Add a path here only with a clear
# reason — the default expectation is that every notebook is registered.
UNREGISTERED_NOTEBOOK_ALLOWLIST: set[str] = {
    "tool_use/tool_search_alternate_approaches.ipynb",
}


@pytest.fixture(scope="module")
def registry() -> list[dict]:
    with open(REGISTRY_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    assert isinstance(data, list), "registry.yaml should be a top-level list of entries"
    return data


@pytest.fixture(scope="module")
def authors() -> dict[str, dict]:
    with open(AUTHORS_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    assert isinstance(data, dict), "authors.yaml should be a top-level mapping"
    return data


@pytest.fixture(scope="module")
def filesystem_notebooks() -> set[str]:
    notebooks = set()
    for path in REPO_ROOT.rglob("*.ipynb"):
        rel = path.relative_to(REPO_ROOT).as_posix()
        if ".ipynb_checkpoints" in rel:
            continue
        notebooks.add(rel)
    return notebooks


class TestRegistryStructure:
    def test_every_entry_has_required_fields(self, registry):
        required = {"title", "description", "path", "authors", "categories"}
        for entry in registry:
            missing = required - entry.keys()
            assert not missing, f"Entry {entry.get('path', '?')} missing fields: {missing}"

    def test_paths_are_relative_ipynb(self, registry):
        for entry in registry:
            path = entry["path"]
            assert not path.startswith("/"), f"{path} should be repo-relative"
            assert path.endswith(".ipynb"), f"{path} should be a .ipynb file"

    def test_no_duplicate_paths(self, registry):
        paths = [entry["path"] for entry in registry]
        duplicates = {p for p in paths if paths.count(p) > 1}
        assert not duplicates, f"Duplicate registry entries: {duplicates}"

    def test_authors_field_is_non_empty_list(self, registry):
        for entry in registry:
            authors_field = entry.get("authors")
            assert isinstance(authors_field, list) and authors_field, (
                f"{entry['path']}: authors must be a non-empty list"
            )

    def test_categories_field_is_non_empty_list(self, registry):
        for entry in registry:
            cats = entry.get("categories")
            assert isinstance(cats, list) and cats, (
                f"{entry['path']}: categories must be a non-empty list"
            )


class TestRegistryFilesystemConsistency:
    def test_every_registered_notebook_exists(self, registry, filesystem_notebooks):
        missing = [entry["path"] for entry in registry if entry["path"] not in filesystem_notebooks]
        assert not missing, (
            f"registry.yaml references notebooks that don't exist on disk: {missing}"
        )

    def test_every_filesystem_notebook_is_registered(self, registry, filesystem_notebooks):
        registered = {entry["path"] for entry in registry}
        unregistered = filesystem_notebooks - registered - UNREGISTERED_NOTEBOOK_ALLOWLIST
        assert not unregistered, (
            "Notebooks exist on disk but are not in registry.yaml. Either add "
            "an entry or, if intentionally excluded, add to "
            "UNREGISTERED_NOTEBOOK_ALLOWLIST in this test file with a reason: "
            f"{sorted(unregistered)}"
        )

    def test_allowlist_entries_still_exist(self, filesystem_notebooks):
        # If an allowlisted notebook is deleted, the allowlist entry should be
        # removed too — otherwise it silently masks future regressions.
        stale = UNREGISTERED_NOTEBOOK_ALLOWLIST - filesystem_notebooks
        assert not stale, (
            f"Stale UNREGISTERED_NOTEBOOK_ALLOWLIST entries (notebook deleted): {stale}"
        )


class TestAuthorReferences:
    def test_every_referenced_author_is_defined(self, registry, authors):
        referenced = {a for entry in registry for a in entry["authors"]}
        undefined = referenced - authors.keys()
        assert not undefined, (
            f"registry.yaml references authors missing from authors.yaml: {sorted(undefined)}"
        )

    def test_every_defined_author_is_used(self, registry, authors):
        # Catches stale author entries from removed notebooks. Soft-warning
        # could be friendlier, but unused entries clutter the website too.
        referenced = {a for entry in registry for a in entry["authors"]}
        unused = set(authors.keys()) - referenced
        assert not unused, (
            f"authors.yaml defines authors not used in registry.yaml: {sorted(unused)}"
        )

    def test_author_entries_have_name_and_avatar(self, authors):
        for username, info in authors.items():
            assert "name" in info, f"author {username!r} missing 'name'"
            assert "avatar" in info, f"author {username!r} missing 'avatar'"

    def test_authors_yaml_is_sorted_case_insensitive(self, authors):
        # The repo enforces case-insensitive sorting via validate_authors_sorted.py.
        # Mirror that contract here so a forgotten entry is caught at test time too.
        keys = list(authors.keys())
        sorted_keys = sorted(keys, key=str.lower)
        assert keys == sorted_keys, (
            "authors.yaml must be sorted alphabetically (case-insensitive). "
            "Run: uv run python scripts/validate_authors_sorted.py --fix"
        )
