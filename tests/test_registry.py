"""Consistency tests for ``registry.yaml`` and ``authors.yaml``.

These tests catch the most common drift between the registry, the authors
manifest, and what actually exists on disk. They run with the rest of the
pytest suite (no API key needed) and complement the network-heavy checks in
``.github/scripts/verify_registry.py``.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
import yaml

PROJECT_ROOT = Path(__file__).parent.parent
REGISTRY_PATH = PROJECT_ROOT / "registry.yaml"
AUTHORS_PATH = PROJECT_ROOT / "authors.yaml"

REQUIRED_FIELDS = {"title", "description", "path", "authors", "categories", "date"}


@pytest.fixture(scope="module")
def registry() -> list[dict]:
    with open(REGISTRY_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    assert isinstance(data, list), "registry.yaml must be a top-level YAML list"
    return data


@pytest.fixture(scope="module")
def authors() -> dict[str, dict]:
    with open(AUTHORS_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    assert isinstance(data, dict), "authors.yaml must be a top-level YAML mapping"
    return data


class TestRegistrySchema:
    """Each registry entry has the fields the website + CI expect."""

    def test_required_fields_present(self, registry):
        missing = []
        for i, entry in enumerate(registry):
            absent = REQUIRED_FIELDS - set(entry)
            if absent:
                missing.append(f"entry {i} ({entry.get('path', '?')}) missing {sorted(absent)}")
        assert not missing, "Missing required fields:\n" + "\n".join(missing)

    def test_date_format(self, registry):
        """Dates must be YYYY-MM-DD strings parseable as ISO dates."""
        bad = []
        for entry in registry:
            date = entry.get("date")
            if not isinstance(date, str):
                bad.append(f"{entry.get('path')}: date is {type(date).__name__}, want str")
                continue
            try:
                datetime.strptime(date, "%Y-%m-%d")
            except ValueError as e:
                bad.append(f"{entry.get('path')}: {e}")
        assert not bad, "Invalid date entries:\n" + "\n".join(bad)

    def test_authors_is_non_empty_list(self, registry):
        bad = []
        for entry in registry:
            authors = entry.get("authors")
            if not isinstance(authors, list) or not authors:
                bad.append(f"{entry.get('path')}: authors must be a non-empty list")
        assert not bad, "\n".join(bad)

    def test_categories_is_non_empty_list(self, registry):
        bad = []
        for entry in registry:
            cats = entry.get("categories")
            if not isinstance(cats, list) or not cats:
                bad.append(f"{entry.get('path')}: categories must be a non-empty list")
        assert not bad, "\n".join(bad)


class TestRegistryPaths:
    def test_paths_exist(self, registry):
        missing = [
            entry["path"]
            for entry in registry
            if not (PROJECT_ROOT / entry.get("path", "")).is_file()
        ]
        assert not missing, "Registry paths that do not exist on disk:\n" + "\n".join(missing)

    def test_paths_are_notebooks(self, registry):
        non_notebooks = [
            entry["path"]
            for entry in registry
            if entry.get("path") and not entry["path"].endswith(".ipynb")
        ]
        assert not non_notebooks, "Non-notebook paths in registry:\n" + "\n".join(non_notebooks)

    def test_paths_are_unique(self, registry):
        seen: dict[str, int] = {}
        for entry in registry:
            seen[entry["path"]] = seen.get(entry["path"], 0) + 1
        dups = [p for p, n in seen.items() if n > 1]
        assert not dups, "Duplicate paths in registry:\n" + "\n".join(dups)


class TestRegistryAuthors:
    def test_all_authors_resolve(self, registry, authors):
        """Every author referenced in registry.yaml must exist in authors.yaml."""
        unknown = set()
        for entry in registry:
            for author in entry.get("authors", []):
                if author not in authors:
                    unknown.add(author)
        assert not unknown, (
            "Authors referenced in registry but missing from authors.yaml:\n"
            + "\n".join(sorted(unknown))
        )


class TestAuthorsManifest:
    def test_sorted_case_insensitive(self, authors):
        """authors.yaml must remain case-insensitive sorted (enforced by hook)."""
        keys = list(authors.keys())
        expected = sorted(keys, key=str.lower)
        assert keys == expected, (
            "authors.yaml is not sorted (case-insensitive). Run `make sort-authors` to fix."
        )

    def test_each_author_has_name(self, authors):
        missing = [k for k, v in authors.items() if not isinstance(v, dict) or not v.get("name")]
        assert not missing, "Authors missing 'name':\n" + "\n".join(missing)
