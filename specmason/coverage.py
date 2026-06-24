"""Requirement-to-test and test-to-requirement coverage.

Coverage is computed in two directions:

- **forward** (requirements/specs -> tests): per accepted behavior criterion,
  whether a scenario exists and a mapped pytest test exists.
- **reverse** (tests -> requirements/specs): per discovered pytest test, whether
  it is mapped, waived, unmapped, invalid, or stale.

Statuses: ``mapped``, ``missing``, ``stale``, ``unmapped``, ``waived``,
``invalid``, ``unknown-authority``. Candidate title matches are hints only
(SML022); IDs are the binding authority.

JSON output is deterministic via :func:`ledgercore.jsonio.dumps_json`.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Literal

from ledgercore.jsonio import dumps_json

from specmason.config import Mode
from specmason.errors import (
    SML011_STALE_MAPPING_TARGET,
    SML012_MISSING_PYTEST_MAPPING,
    SML013_UNMAPPED_PYTEST_TEST,
    SML020_NO_REQLEDGER_MANIFEST_STANDALONE,
    SML021_UNKNOWN_REQUIREMENT_AUTHORITY,
    SML022_CANDIDATE_MATCH_NOT_BINDING,
    Finding,
    Findings,
)
from specmason.gherkin.model import Feature
from specmason.ids import extract_identity, slugify
from specmason.mappings import MappingInventory, TestMapping
from specmason.requirements import RequirementsIndex

CoverageStatus = Literal[
    "mapped", "missing", "stale", "unmapped", "waived", "invalid", "unknown-authority"
]


@dataclass(frozen=True)
class ScenarioRef:
    """A reference to a scenario that covers a criterion."""

    feature: str
    name: str
    line: int

    def to_dict(self) -> dict[str, object]:
        return {"feature": self.feature, "name": self.name, "line": self.line}


@dataclass(frozen=True)
class CriterionCoverage:
    """Forward coverage for one accepted behavior criterion (or standalone id)."""

    req_id: str
    ac_id: str
    statement: str
    status: CoverageStatus
    scenarios: tuple[ScenarioRef, ...] = ()
    tests: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "req_id": self.req_id,
            "ac_id": self.ac_id,
            "statement": self.statement,
            "status": self.status,
            "scenarios": [s.to_dict() for s in self.scenarios],
            "tests": list(self.tests),
        }


@dataclass(frozen=True)
class TestCoverage:
    """Reverse coverage for one discovered pytest test."""

    nodeid: str
    status: CoverageStatus
    mappings: tuple[tuple[str, str], ...] = ()
    reason: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "nodeid": self.nodeid,
            "status": self.status,
            "mappings": [{"req_id": r, "ac_id": a} for r, a in self.mappings],
            "reason": self.reason,
        }


@dataclass(frozen=True)
class CoverageReport:
    """A full coverage report in both directions."""

    mode: str
    forward: tuple[CriterionCoverage, ...] = ()
    reverse: tuple[TestCoverage, ...] = ()
    findings: Findings = field(default_factory=Findings)

    @property
    def has_errors(self) -> bool:
        return self.findings.has_errors

    def counts(self) -> dict[str, object]:
        forward_counts: dict[str, int] = defaultdict(int)
        for item in self.forward:
            forward_counts[item.status] += 1
        reverse_counts: dict[str, int] = defaultdict(int)
        for item in self.reverse:
            reverse_counts[item.status] += 1
        return {
            "mode": self.mode,
            "forward": dict(forward_counts),
            "reverse": dict(reverse_counts),
            "errors": len(self.findings.errors),
        }

    def to_dict(self) -> dict[str, object]:
        return {
            "mode": self.mode,
            "forward": [c.to_dict() for c in self.forward],
            "reverse": [t.to_dict() for t in self.reverse],
            "findings": self.findings.to_list(),
            "summary": self.counts(),
        }

    def to_json(self) -> str:
        return dumps_json(self.to_dict(), indent=2, sort_keys=True)


def _index_scenarios(
    features: list[Feature],
) -> tuple[
    dict[str, list[ScenarioRef]],
    dict[str, list[ScenarioRef]],
    dict[str, Feature],
]:
    by_ac: dict[str, list[ScenarioRef]] = defaultdict(list)
    by_req: dict[str, list[ScenarioRef]] = defaultdict(list)
    by_path: dict[str, Feature] = {}
    for feature in features:
        by_path[feature.path] = feature
        for scenario in feature.iter_scenarios():
            req_id, ac_id = extract_identity(list(scenario.tags))
            if req_id is None or ac_id is None:
                continue
            ref = ScenarioRef(feature.path, scenario.name, scenario.line)
            by_ac[ac_id].append(ref)
            by_req[req_id].append(ref)
    return by_ac, by_req, by_path


def _tests_by_ac(inventory: MappingInventory) -> dict[str, list[str]]:
    mapping: dict[str, list[str]] = defaultdict(list)
    for test in inventory.tests:
        if test.is_mapped:
            for _, ac_id in test.criterion_ids():
                mapping[ac_id].append(test.nodeid)
    for ac_id in mapping:
        mapping[ac_id] = sorted(set(mapping[ac_id]))
    return mapping


def _candidate_hint(nodeid: str, by_ac: dict[str, list[ScenarioRef]]) -> Finding | None:
    """Return an SML022 info hint if a scenario title resembles the test name."""
    test_slug = slugify(nodeid.rsplit("::", 1)[-1].removeprefix("test_"))
    if not test_slug:
        return None
    for refs in by_ac.values():
        for ref in refs:
            scenario_slug = slugify(ref.name)
            if scenario_slug and (
                test_slug in scenario_slug or scenario_slug in test_slug
            ):
                return Finding(
                    SML022_CANDIDATE_MATCH_NOT_BINDING,
                    "info",
                    f"test {nodeid} resembles scenario {ref.name!r} "
                    f"(hint, not a binding)",
                    ref.feature,
                )
    return None


def _build_forward(
    features: list[Feature],
    inventory: MappingInventory,
    *,
    index: RequirementsIndex | None,
    by_ac: dict[str, list[ScenarioRef]],
    tests_by_ac: dict[str, list[str]],
    findings: Findings,
) -> tuple[list[CriterionCoverage], Findings]:
    forward: list[CriterionCoverage] = []

    if index is not None:
        for req in sorted(index.requirements, key=lambda r: r.id):
            for crit in sorted(req.criteria, key=lambda c: c.id):
                if crit.id not in index.accepted_behavior_ac_ids:
                    continue
                scenarios = tuple(by_ac.get(crit.id, ()))
                tests = tuple(tests_by_ac.get(crit.id, ()))
                if scenarios and tests:
                    status: CoverageStatus = "mapped"
                else:
                    status = "missing"
                    findings = findings.append(
                        Finding(
                            SML012_MISSING_PYTEST_MAPPING,
                            "error",
                            (
                                f"accepted behavior criterion {crit.id} "
                                f"({req.id}) lacks scenario/test coverage"
                            ),
                            req.id,
                        )
                    )
                forward.append(
                    CriterionCoverage(
                        req_id=req.id,
                        ac_id=crit.id,
                        statement=crit.statement,
                        status=status,
                        scenarios=scenarios,
                        tests=tests,
                    )
                )
        return forward, findings

    # Standalone forward: per distinct scenario identity, unknown authority.
    identities: set[tuple[str, str]] = set()
    for feature in features:
        for scenario in feature.iter_scenarios():
            req_id, ac_id = extract_identity(list(scenario.tags))
            if req_id and ac_id:
                identities.add((req_id, ac_id))
    for req_id, ac_id in sorted(identities):
        scenarios = tuple(by_ac.get(ac_id, ()))
        tests = tuple(tests_by_ac.get(ac_id, ()))
        status = "mapped" if (scenarios and tests) else "unknown-authority"
        forward.append(
            CriterionCoverage(
                req_id=req_id,
                ac_id=ac_id,
                statement="",
                status=status,
                scenarios=scenarios,
                tests=tests,
            )
        )
    return forward, findings


def _classify_mapped_test(
    test: TestMapping,
    *,
    index: RequirementsIndex | None,
    by_path: dict[str, Feature],
) -> tuple[CoverageStatus, str]:
    statuses: list[CoverageStatus] = []
    for req_id, ac_id in test.criterion_ids():
        feature_hint = next(
            (
                m.feature
                for m in test.mappings
                if m.req_id == req_id and m.ac_id == ac_id
            ),
            "",
        )
        if index is not None:
            if ac_id not in index.criterion_ids or req_id not in index.requirement_ids:
                statuses.append("invalid")
                continue
        if feature_hint:
            feature = by_path.get(feature_hint)
            if feature is None:
                statuses.append("stale")
                continue
            found = any(
                extract_identity(list(s.tags)) == (req_id, ac_id)
                for s in feature.iter_scenarios()
            )
            statuses.append("mapped" if found else "stale")
        else:
            statuses.append("mapped")
    if "invalid" in statuses:
        return "invalid", "mapping references unknown requirement or criterion"
    if "stale" in statuses:
        return "stale", "mapping target scenario no longer present"
    return "mapped", ""


def _build_reverse(
    inventory: MappingInventory,
    *,
    index: RequirementsIndex | None,
    by_path: dict[str, Feature],
    by_ac: dict[str, list[ScenarioRef]],
    findings: Findings,
) -> tuple[list[TestCoverage], Findings]:
    reverse: list[TestCoverage] = []
    for test in inventory.tests:
        if test.is_waived:
            reverse.append(TestCoverage(test.nodeid, "waived", test.criterion_ids()))
            continue
        if not test.is_mapped:
            findings = findings.append(
                Finding(
                    SML013_UNMAPPED_PYTEST_TEST,
                    "error",
                    f"pytest test {test.nodeid} is not mapped to a requirement",
                    test.nodeid,
                )
            )
            hint = _candidate_hint(test.nodeid, by_ac)
            if hint is not None:
                findings = findings.append(hint)
            reverse.append(TestCoverage(test.nodeid, "unmapped"))
            continue

        status, reason = _classify_mapped_test(test, index=index, by_path=by_path)
        if status == "invalid":
            findings = findings.append(
                Finding(
                    SML011_STALE_MAPPING_TARGET,
                    "error",
                    f"mapping for {test.nodeid} targets unknown authority: {reason}",
                    test.nodeid,
                )
            )
        elif status == "stale":
            findings = findings.append(
                Finding(
                    SML011_STALE_MAPPING_TARGET,
                    "error",
                    f"mapping for {test.nodeid} is stale: {reason}",
                    test.nodeid,
                )
            )
        reverse.append(
            TestCoverage(test.nodeid, status, test.criterion_ids(), reason=reason)
        )
    return reverse, findings


def build_coverage(
    features: list[Feature],
    inventory: MappingInventory,
    *,
    index: RequirementsIndex | None = None,
    mode: Mode | str = Mode.STANDALONE,
) -> CoverageReport:
    """Compute coverage in both directions."""
    mode_value = mode.value if isinstance(mode, Mode) else str(mode)
    findings = Findings()

    by_ac, _by_req, by_path = _index_scenarios(features)
    tests_by_ac = _tests_by_ac(inventory)

    if mode_value == Mode.INTEGRATED.value and index is None:
        findings = findings.append(
            Finding(
                SML021_UNKNOWN_REQUIREMENT_AUTHORITY,
                "warning",
                "integrated mode requested but no requirement index available",
            )
        )

    forward, findings = _build_forward(
        features,
        inventory,
        index=index,
        by_ac=by_ac,
        tests_by_ac=tests_by_ac,
        findings=findings,
    )
    reverse, findings = _build_reverse(
        inventory, index=index, by_path=by_path, by_ac=by_ac, findings=findings
    )

    return CoverageReport(
        mode=mode_value,
        forward=tuple(forward),
        reverse=tuple(reverse),
        findings=findings,
    )


def standalone_diagnostic() -> Finding:
    """The informational SML020 finding emitted in standalone mode."""
    return Finding(
        SML020_NO_REQLEDGER_MANIFEST_STANDALONE,
        "info",
        "no ReqLedger manifest found; running in standalone mode; "
        "requirement authority checks are skipped",
    )


def render_markdown(report: CoverageReport) -> str:
    """Render a deterministic Markdown coverage report."""
    lines: list[str] = []
    counts = report.counts()
    lines.append("# SpecMason Coverage Report")
    lines.append("")
    lines.append(f"Mode: `{report.mode}`")
    lines.append("")

    lines.append("## Forward (requirements/specs -> tests)")
    lines.append("")
    lines.append("| Requirement | Criterion | Statement | Status | Scenarios | Tests |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for item in report.forward:
        scenarios = "; ".join(s.feature for s in item.scenarios)
        lines.append(
            f"| {item.req_id} | {item.ac_id} | {item.statement} | {item.status} | "
            f"{scenarios or '-'} | {'; '.join(item.tests) or '-'} |"
        )
    if not report.forward:
        lines.append("| _none_ | | | | | |")
    lines.append("")

    lines.append("## Reverse (tests -> requirements/specs)")
    lines.append("")
    lines.append("| Test | Status | Mappings |")
    lines.append("| --- | --- | --- |")
    for item in report.reverse:
        mappings = "; ".join(f"{r}/{a}" for r, a in item.mappings) or "-"
        lines.append(f"| `{item.nodeid}` | {item.status} | {mappings} |")
    if not report.reverse:
        lines.append("| _none_ | | |")
    lines.append("")

    lines.append("## Summary")
    lines.append("")
    lines.append("```json")
    lines.append(dumps_json(counts, indent=2, sort_keys=True).rstrip())
    lines.append("```")
    lines.append("")

    if report.findings:
        lines.append("## Findings")
        lines.append("")
        for finding in report.findings:
            lines.append(f"- {finding.render()}")
        lines.append("")

    return "\n".join(lines)


__all__ = [
    "CoverageReport",
    "CoverageStatus",
    "CriterionCoverage",
    "ScenarioRef",
    "TestCoverage",
    "build_coverage",
    "render_markdown",
    "standalone_diagnostic",
]
