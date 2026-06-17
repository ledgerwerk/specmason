"""Tests for the ReqLedger manifest reader (read-only, no reqledger import)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from specmason import requirements as reqmod
from specmason.requirements import (
    Criterion,
    Requirement,
    RequirementsError,
    RequirementsIndex,
    build_index,
    load_manifest,
)


def _manifest(requirements: list) -> str:
    return json.dumps(
        {"schema_version": 1, "tool": "reqledger", "requirements": requirements}
    )


def _basic_manifest() -> str:
    return _manifest(
        [
            {
                "id": "REQ-0002",
                "title": "Other",
                "kind": "functional",
                "status": "accepted",
                "priority": "should",
                "criteria": [],
                "refs": {},
            },
            {
                "id": "REQ-0001",
                "title": "Login",
                "kind": "functional",
                "status": "accepted",
                "priority": "must",
                "criteria": [
                    {
                        "id": "AC-0001",
                        "statement": "reject invalid password",
                        "verification": "behavior",
                        "status": "accepted",
                        "tags": [],
                    },
                    {
                        "id": "AC-0002",
                        "statement": "audit log",
                        "verification": "inspection",
                        "status": "accepted",
                    },
                    {
                        "id": "AC-0003",
                        "statement": "draft",
                        "verification": "behavior",
                        "status": "draft",
                    },
                ],
                "refs": {"specs": ["specs/behavior/features/auth.feature"]},
            },
        ]
    )


def test_load_manifest_builds_indexes(tmp_path: Path) -> None:
    path = tmp_path / "manifest.json"
    path.write_text(_basic_manifest(), encoding="utf-8")
    index = load_manifest(path)
    # requirements sorted by id
    assert [r.id for r in index.requirements] == ["REQ-0001", "REQ-0002"]
    assert index.requirement_ids == {"REQ-0001", "REQ-0002"}
    assert index.criterion_ids == {"AC-0001", "AC-0002", "AC-0003"}
    req_id, crit = index.criterion("AC-0001")  # type: ignore[misc]
    assert req_id == "REQ-0001"
    assert crit.statement == "reject invalid password"


def test_accepted_behavior_criteria_filtered(tmp_path: Path) -> None:
    path = tmp_path / "manifest.json"
    path.write_text(_basic_manifest(), encoding="utf-8")
    index = load_manifest(path)
    # AC-0001: accepted behavior -> included; AC-0002: inspection -> excluded;
    # AC-0003: draft -> excluded.
    assert index.is_accepted_behavior("AC-0001")
    assert not index.is_accepted_behavior("AC-0002")
    assert not index.is_accepted_behavior("AC-0003")
    assert index.accepted_behavior_ac_ids == frozenset({"AC-0001"})


def test_refs_parsed_into_spec_refs(tmp_path: Path) -> None:
    path = tmp_path / "manifest.json"
    path.write_text(_basic_manifest(), encoding="utf-8")
    index = load_manifest(path)
    req = index.by_id["REQ-0001"]
    assert req.spec_refs == ("specs/behavior/features/auth.feature",)


def test_load_manifest_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(RequirementsError):
        load_manifest(tmp_path / "nope.json")


def test_load_manifest_invalid_json_raises(tmp_path: Path) -> None:
    path = tmp_path / "manifest.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(RequirementsError):
        load_manifest(path)


def test_load_manifest_missing_requirements_key_raises(tmp_path: Path) -> None:
    path = tmp_path / "manifest.json"
    path.write_text('{"schema_version":1,"tool":"reqledger"}', encoding="utf-8")
    with pytest.raises(RequirementsError):
        load_manifest(path)


def test_build_index_empty() -> None:
    index = build_index([])
    assert isinstance(index, RequirementsIndex)
    assert index.requirement_ids == frozenset()
    assert index.criterion_ids == frozenset()


def test_specmason_does_not_import_reqledger() -> None:
    import sys

    assert "reqledger" not in sys.modules


def test_requirement_and_criterion_are_frozen() -> None:
    crit = Criterion(
        id="AC-0001", statement="s", verification="behavior", status="accepted"
    )
    req = Requirement(
        id="REQ-0001", title="t", kind="functional", status="accepted", priority="must"
    )
    with pytest.raises(AttributeError):
        crit.id = "x"  # type: ignore[misc]
    with pytest.raises(AttributeError):
        req.id = "x"  # type: ignore[misc]
    assert reqmod is not None  # module import sanity
