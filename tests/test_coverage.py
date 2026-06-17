"""Tests for coverage in both directions (standalone + integrated)."""

from __future__ import annotations

from specmason.config import Mode
from specmason.coverage import build_coverage, render_markdown
from specmason.errors import (
    SML011_STALE_MAPPING_TARGET,
    SML012_MISSING_PYTEST_MAPPING,
    SML013_UNMAPPED_PYTEST_TEST,
    SML022_CANDIDATE_MATCH_NOT_BINDING,
)
from specmason.gherkin.parser import parse_feature
from specmason.mappings import (
    InlineWaiver,
    Mapping,
    MappingInventory,
    PolicyWaiver,
    TestMapping,
)
from specmason.requirements import Criterion, Requirement, build_index


def _feature(path: str, req: str, ac: str, name: str = "S") -> object:
    text = (
        f"Feature: F\n"
        f"  @req-{req} @ac-{ac}\n"
        f"  Scenario: {name}\n"
        f"    Then ok\n"
    )
    return parse_feature(text, path=path)


def _test(nodeid: str, mappings=(), waiver=None, central=None) -> TestMapping:
    return TestMapping(
        nodeid=nodeid,
        file=nodeid.split("::")[0],
        name=nodeid.split("::")[-1],
        class_name="",
        lineno=1,
        mappings=tuple(mappings),
        inline_waiver=waiver,
        central_waiver=central,
    )


def _index() -> object:
    req = Requirement(
        id="REQ-0001",
        title="Login",
        kind="functional",
        status="accepted",
        priority="must",
        criteria=(
            Criterion(
                id="AC-0001",
                statement="reject invalid password",
                verification="behavior",
                status="accepted",
            ),
            Criterion(
                id="AC-0002",
                statement="audit log",
                verification="behavior",
                status="accepted",
            ),
        ),
    )
    return build_index([req])


def test_integrated_reports_missing_accepted_criterion() -> None:
    features = [_feature("specs/auth.feature", "REQ-0001", "AC-0001")]  # type: ignore[list-item]
    inventory = MappingInventory(
        tests=(
            _test(
                "tests/t.py::test_reject",
                mappings=(Mapping(req_id="REQ-0001", ac_id="AC-0001"),),
            ),
        ),
    )
    report = build_coverage(features, inventory, index=_index(), mode=Mode.INTEGRATED)  # type: ignore[arg-type]
    by_ac = {c.ac_id: c.status for c in report.forward}
    assert by_ac["AC-0001"] == "mapped"
    assert by_ac["AC-0002"] == "missing"
    assert any(f.code == SML012_MISSING_PYTEST_MAPPING for f in report.findings)


def test_integrated_reports_unmapped_tests() -> None:
    features = []  # type: ignore[list-item]
    inventory = MappingInventory(
        tests=(_test("tests/t.py::test_orphan"),),
    )
    report = build_coverage(features, inventory, index=_index(), mode=Mode.INTEGRATED)  # type: ignore[arg-type]
    statuses = {t.nodeid: t.status for t in report.reverse}
    assert statuses["tests/t.py::test_orphan"] == "unmapped"
    assert any(f.code == SML013_UNMAPPED_PYTEST_TEST for f in report.findings)


def test_waived_tests_are_waived_not_mapped() -> None:
    features = []  # type: ignore[list-item]
    inventory = MappingInventory(
        tests=(
            _test(
                "tests/t.py::test_helper",
                waiver=InlineWaiver(reason="unit helper"),
            ),
            _test(
                "tests/t.py::test_central",
                central=PolicyWaiver(
                    nodeid="tests/t.py::test_central",
                    reason="internal",
                ),
            ),
        ),
    )
    report = build_coverage(features, inventory, index=_index(), mode=Mode.INTEGRATED)  # type: ignore[arg-type]
    statuses = {t.nodeid: t.status for t in report.reverse}
    assert statuses["tests/t.py::test_helper"] == "waived"
    assert statuses["tests/t.py::test_central"] == "waived"
    assert not any(f.code == SML013_UNMAPPED_PYTEST_TEST for f in report.findings)


def test_candidate_match_is_hint_only() -> None:
    features = [
        _feature(
            "specs/auth.feature",
            "REQ-0001",
            "AC-0001",
            name="reject invalid password",
        )
    ]  # type: ignore[list-item]
    inventory = MappingInventory(
        tests=(_test("tests/t.py::test_reject_invalid_password"),),
    )
    report = build_coverage(features, inventory, index=_index(), mode=Mode.INTEGRATED)  # type: ignore[arg-type]
    # unmapped test whose name resembles a scenario -> info hint, but still unmapped
    statuses = {t.nodeid: t.status for t in report.reverse}
    assert statuses["tests/t.py::test_reject_invalid_password"] == "unmapped"
    assert any(f.code == SML022_CANDIDATE_MATCH_NOT_BINDING for f in report.findings)
    hint = next(
        f for f in report.findings
        if f.code == SML022_CANDIDATE_MATCH_NOT_BINDING
    )
    assert hint.severity == "info"


def test_stale_mapping_when_feature_target_missing() -> None:
    features = []  # type: ignore[list-item]
    inventory = MappingInventory(
        tests=(
            _test(
                "tests/t.py::test_x",
                mappings=(
                    Mapping(
                        req_id="REQ-0001",
                        ac_id="AC-0001",
                        feature="specs/missing.feature",
                    ),
                ),
            ),
        ),
    )
    report = build_coverage(features, inventory, index=_index(), mode=Mode.INTEGRATED)  # type: ignore[arg-type]
    statuses = {t.nodeid: t.status for t in report.reverse}
    assert statuses["tests/t.py::test_x"] == "stale"
    assert any(f.code == SML011_STALE_MAPPING_TARGET for f in report.findings)


def test_invalid_mapping_when_authority_unknown() -> None:
    features = []  # type: ignore[list-item]
    inventory = MappingInventory(
        tests=(
            _test(
                "tests/t.py::test_x",
                mappings=(Mapping(req_id="REQ-0099", ac_id="AC-0099"),),
            ),
        ),
    )
    report = build_coverage(features, inventory, index=_index(), mode=Mode.INTEGRATED)  # type: ignore[arg-type]
    statuses = {t.nodeid: t.status for t in report.reverse}
    assert statuses["tests/t.py::test_x"] == "invalid"


def test_standalone_reports_unknown_authority_without_index() -> None:
    features = [_feature("specs/auth.feature", "REQ-0001", "AC-0001")]  # type: ignore[list-item]
    inventory = MappingInventory(
        tests=(
            _test(
                "tests/t.py::test_reject",
                mappings=(Mapping(req_id="REQ-0001", ac_id="AC-0001"),),
            ),
        ),
    )
    report = build_coverage(features, inventory, index=None, mode=Mode.STANDALONE)
    by_ac = {c.ac_id: c.status for c in report.forward}
    # has both scenario and test -> mapped; unknown authority only for gaps
    assert by_ac["AC-0001"] == "mapped"


def test_coverage_to_json_is_valid() -> None:
    import json

    features = [_feature("specs/auth.feature", "REQ-0001", "AC-0001")]  # type: ignore[list-item]
    inventory = MappingInventory(
        tests=(
            _test(
                "tests/t.py::test_reject",
                mappings=(Mapping(req_id="REQ-0001", ac_id="AC-0001"),),
            ),
        ),
    )
    report = build_coverage(features, inventory, index=_index(), mode=Mode.INTEGRATED)  # type: ignore[arg-type]
    data = json.loads(report.to_json())
    assert data["mode"] == "integrated"
    assert isinstance(data["forward"], list)
    assert isinstance(data["reverse"], list)


def test_render_markdown_contains_sections() -> None:
    features = [_feature("specs/auth.feature", "REQ-0001", "AC-0001")]  # type: ignore[list-item]
    inventory = MappingInventory(
        tests=(
            _test(
                "tests/t.py::test_reject",
                mappings=(Mapping(req_id="REQ-0001", ac_id="AC-0001"),),
            ),
        ),
    )
    report = build_coverage(features, inventory, index=_index(), mode=Mode.INTEGRATED)  # type: ignore[arg-type]
    md = render_markdown(report)
    assert "Forward" in md
    assert "Reverse" in md
    assert "Summary" in md
