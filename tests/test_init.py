"""Tests for ``specmason init`` (workspace layout + idempotency)."""

from __future__ import annotations

import json
from pathlib import Path

from specmason.init import init_workspace

EXPECTED_DIRS = (
    "specs/behavior/features",
    "specs/behavior/mappings",
    "specs/behavior/evidence",
    "specs/behavior/reports/specmason",
)
EXPECTED_FILES = (
    "specmason.toml",
    "specs/behavior/README.md",
    "specs/behavior/mappings/intentional-unmapped.json",
)


def test_init_creates_expected_layout(tmp_path: Path) -> None:
    result = init_workspace(tmp_path)
    for rel in EXPECTED_DIRS:
        assert (tmp_path / rel).is_dir(), f"missing dir {rel}"
    for rel in EXPECTED_FILES:
        assert (tmp_path / rel).is_file(), f"missing file {rel}"
    # the unmapped policy is valid JSON
    policy = json.loads(
        (tmp_path / "specs/behavior/mappings/intentional-unmapped.json").read_text()
    )
    assert policy == {"schema_version": 1, "items": []}
    assert "specmason.toml" in result.created
    assert all(d in result.created for d in EXPECTED_DIRS)


def test_init_is_idempotent(tmp_path: Path) -> None:
    first = init_workspace(tmp_path)
    second = init_workspace(tmp_path)
    assert first.created  # first run created things
    assert second.created == ()  # second run created nothing new
    assert set(EXPECTED_FILES).issubset(set(second.skipped))
    assert set(EXPECTED_DIRS).issubset(set(second.existing))


def test_init_does_not_overwrite_without_force(tmp_path: Path) -> None:
    init_workspace(tmp_path)
    custom = tmp_path / "specmason.toml"
    custom.write_text("# my custom config\n", encoding="utf-8")
    result = init_workspace(tmp_path)
    assert "specmason.toml" in result.skipped
    assert custom.read_text() == "# my custom config\n"


def test_init_force_overwrites(tmp_path: Path) -> None:
    init_workspace(tmp_path)
    custom = tmp_path / "specmason.toml"
    custom.write_text("# my custom config\n", encoding="utf-8")
    result = init_workspace(tmp_path, force=True)
    assert "specmason.toml" in result.overwritten
    assert "my custom config" not in custom.read_text()
