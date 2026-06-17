"""SpecMason workspace initialization.

``init`` creates the documented, visible workspace layout and is idempotent: it
never overwrites user-authored files unless ``--force`` is given.

All writes go through ledgercore (:func:`ledgercore.io.ensure_dir` for
directories and :func:`ledgercore.atomic.atomic_write_text` for files) so file
creation is crash-safe and deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ledgercore.atomic import atomic_write_text
from ledgercore.io import ensure_dir

# Default config text written by ``specmason init`` (mirrors the brief).
INIT_CONFIG_TEXT = """\
schema_version = 1

[paths]
behavior_root = "specs/behavior"
features_dir = "specs/behavior/features"
manifest = "specs/behavior/manifest.json"
mappings_dir = "specs/behavior/mappings"
evidence_dir = "specs/behavior/evidence"
reports_dir = "specs/behavior/reports"
reports_state_dir = "specs/behavior/reports/specmason"
tests_dir = "tests"

[requirements]
manifest = "requirements/manifest.json"
required = false

[gherkin]
default_keyword = "Scenario"
require_req_tag = true
require_ac_tag = true
allow_markdown_gherkin = false
official_parser = false

[pytest]
mapping_comment_prefix = "specmason"
short_mapping_comment_prefix = "sm"
intentional_unmapped_policy = "specs/behavior/mappings/intentional-unmapped.json"
"""

INIT_README_TEXT = """\
# Behavior specifications

This directory holds SpecMason behavior artifacts: Gherkin feature files,
mapping inventories, evidence, and generated reports.

SpecMason is diagnostic: it checks whether behavior specs, pytest tests, and
evidence prove accepted ReqLedger criteria. Requirements are owned by ReqLedger.
"""

INIT_UNMAPPED_POLICY_TEXT = """\
{
  "schema_version": 1,
  "items": []
}
"""

# Relative directories created by ``specmason init``.
INIT_DIRS: tuple[str, ...] = (
    "specs/behavior/features",
    "specs/behavior/mappings",
    "specs/behavior/evidence",
    "specs/behavior/reports/specmason",
)

# Relative (path, content) files written by ``specmason init``.
INIT_FILES: tuple[tuple[str, str], ...] = (
    ("specmason.toml", INIT_CONFIG_TEXT),
    ("specs/behavior/README.md", INIT_README_TEXT),
    ("specs/behavior/mappings/intentional-unmapped.json", INIT_UNMAPPED_POLICY_TEXT),
)


@dataclass(frozen=True)
class InitResult:
    """Outcome of an :func:`init_workspace` run."""

    root: Path
    created: tuple[str, ...] = ()
    existing: tuple[str, ...] = ()
    skipped: tuple[str, ...] = ()
    overwritten: tuple[str, ...] = ()
    errors: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, object]:
        return {
            "root": str(self.root),
            "created": list(self.created),
            "existing": list(self.existing),
            "skipped": list(self.skipped),
            "overwritten": list(self.overwritten),
            "errors": list(self.errors),
        }


def init_workspace(root: Path | str, *, force: bool = False) -> InitResult:
    """Initialize the SpecMason workspace at ``root``.

    Idempotent: existing files are left untouched unless ``force`` is set.
    """
    workspace = Path(root).resolve()
    ensure_dir(workspace)

    created: list[str] = []
    existing: list[str] = []
    skipped: list[str] = []
    overwritten: list[str] = []

    for rel in INIT_DIRS:
        path = workspace / rel
        if path.is_dir():
            existing.append(rel)
        else:
            ensure_dir(path)
            created.append(rel)

    for rel, content in INIT_FILES:
        path = workspace / rel
        if path.is_file():
            if force:
                atomic_write_text(path, content)
                overwritten.append(rel)
            else:
                skipped.append(rel)
        else:
            atomic_write_text(path, content)
            created.append(rel)

    return InitResult(
        root=workspace,
        created=tuple(created),
        existing=tuple(existing),
        skipped=tuple(skipped),
        overwritten=tuple(overwritten),
    )


__all__ = [
    "INIT_CONFIG_TEXT",
    "INIT_DIRS",
    "INIT_FILES",
    "INIT_README_TEXT",
    "INIT_UNMAPPED_POLICY_TEXT",
    "InitResult",
    "init_workspace",
]
