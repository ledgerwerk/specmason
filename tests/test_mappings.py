"""Tests for mapping comment parsing and intentional-unmapped policy."""

from __future__ import annotations

import json
from pathlib import Path

from specmason.errors import (
    SML010_INVALID_MAPPING_COMMENT,
    SML014_INVALID_INTENTIONAL_UNMAPPED_POLICY,
    SML015_EXPIRED_WAIVER,
    SML016_MISSING_WAIVER_REASON,
)
from specmason.mappings import (
    Mapping,
    build_inventory,
    load_intentional_unmapped_policy,
    parse_comment,
    parse_preceding_comments,
)
from specmason.pytest_discovery import DiscoveredTest


def test_parse_full_mapping_comment() -> None:
    parsed = parse_comment(
        "# specmason: req=REQ-0001 ac=AC-0001 feature=specs/x.feature"
    )
    assert isinstance(parsed, Mapping)
    assert parsed.req_id == "REQ-0001"
    assert parsed.ac_id == "AC-0001"
    assert parsed.feature == "specs/x.feature"


def test_parse_short_mapping_comment() -> None:
    parsed = parse_comment("# sm: req=REQ-0001 ac=AC-0001")
    assert isinstance(parsed, Mapping)
    assert parsed.req_id == "REQ-0001"


def test_parse_inline_waiver_comment() -> None:
    parsed = parse_comment(
        "# specmason: unmapped=unit helper; no user-visible behavior"
    )
    assert parsed is not None
    assert not isinstance(parsed, Mapping)
    assert parsed.reason == "unit helper; no user-visible behavior"


def test_parse_non_specmason_comment_is_none() -> None:
    assert parse_comment("# just a note") is None
    assert parse_comment("def test_x(): pass") is None


def test_parse_preceding_comments_stacks_mappings_and_waiver() -> None:
    comments = (
        "# sm: req=REQ-0001 ac=AC-0001",
        "# sm: req=REQ-0002 ac=AC-0002",
        "# specmason: unmapped=reason",
    )
    mappings, waiver = parse_preceding_comments(comments)
    assert len(mappings) == 2
    assert waiver is not None
    assert waiver.reason == "reason"


def _policy(items: list) -> str:
    return json.dumps({"schema_version": 1, "items": items})


def test_load_policy_valid(tmp_path: Path) -> None:
    path = tmp_path / "policy.json"
    path.write_text(
        _policy([{"nodeid": "tests/test_x.py::test_a", "reason": "internal"}]),
        encoding="utf-8",
    )
    waivers, findings = load_intentional_unmapped_policy(path)
    assert "tests/test_x.py::test_a" in waivers
    assert not findings.has_errors


def test_load_policy_missing_reason_is_error(tmp_path: Path) -> None:
    path = tmp_path / "policy.json"
    path.write_text(
        _policy([{"nodeid": "tests/test_x.py::test_a", "reason": ""}]),
        encoding="utf-8",
    )
    _, findings = load_intentional_unmapped_policy(path)
    assert any(f.code == SML016_MISSING_WAIVER_REASON for f in findings)


def test_load_policy_expired_waiver_is_error(tmp_path: Path) -> None:
    path = tmp_path / "policy.json"
    path.write_text(
        _policy(
            [
                {
                    "nodeid": "tests/test_x.py::test_a",
                    "reason": "internal",
                    "expires": "2000-01-01",
                }
            ]
        ),
        encoding="utf-8",
    )
    _, findings = load_intentional_unmapped_policy(path)
    assert any(f.code == SML015_EXPIRED_WAIVER for f in findings)


def test_load_policy_missing_file_is_empty(tmp_path: Path) -> None:
    waivers, findings = load_intentional_unmapped_policy(tmp_path / "nope.json")
    assert waivers == {}
    assert not findings.has_errors


def test_load_policy_invalid_json_is_error(tmp_path: Path) -> None:
    path = tmp_path / "policy.json"
    path.write_text("{bad", encoding="utf-8")
    _, findings = load_intentional_unmapped_policy(path)
    assert any(f.code == SML014_INVALID_INTENTIONAL_UNMAPPED_POLICY for f in findings)


def _discovered(
    nodeid: str, comments: tuple[str, ...], *, file: str = "tests/t.py", lineno: int = 1
) -> DiscoveredTest:
    return DiscoveredTest(
        nodeid=nodeid,
        file=file,
        name=nodeid.split("::")[-1],
        class_name="",
        lineno=lineno,
        preceding_comments=comments,
    )


def test_build_inventory_resolves_statuses() -> None:
    discovered = [
        _discovered("tests/t.py::test_mapped", ("# sm: req=REQ-0001 ac=AC-0001",)),
        _discovered("tests/t.py::test_waived", ("# specmason: unmapped=internal",)),
        _discovered("tests/t.py::test_plain", ()),
    ]
    inventory = build_inventory(discovered)
    by_node = {t.nodeid: t for t in inventory.tests}
    assert by_node["tests/t.py::test_mapped"].status == "mapped"
    assert by_node["tests/t.py::test_waived"].status == "waived"
    assert by_node["tests/t.py::test_plain"].status == "unmapped"


def test_build_inventory_applies_central_waivers() -> None:
    discovered = [_discovered("tests/t.py::test_w", ())]  # no inline mapping
    from specmason.mappings import PolicyWaiver

    central = {
        "tests/t.py::test_w": PolicyWaiver(nodeid="tests/t.py::test_w", reason="r")
    }
    inventory = build_inventory(discovered, central_waivers=central)
    assert inventory.tests[0].status == "waived"
    assert inventory.tests[0].central_waiver is not None


def test_build_inventory_flags_invalid_mapping() -> None:
    # req= with empty value is invalid
    discovered = [_discovered("tests/t.py::test_bad", ("# sm: ac=AC-0001",), lineno=5)]
    inventory = build_inventory(discovered)
    assert any(f.code == SML010_INVALID_MAPPING_COMMENT for f in inventory.findings)
