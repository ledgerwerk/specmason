"""Review orchestration: check + coverage + evidence summary.

The ``review`` command runs ``check`` and ``coverage`` and, when evidence is
present, summarizes it. Final reports are written deterministically to
``specs/behavior/reports/specmason/``:

- ``coverage.md`` (human-readable Markdown)
- ``coverage.json`` (machine-readable)
- ``mappings.json`` (full mapping inventory)

All writes use :func:`ledgercore.atomic.atomic_write_text` and
:func:`ledgercore.jsonio.dumps_json`.
"""

from __future__ import annotations

from dataclasses import dataclass

from ledgercore.atomic import atomic_write_text
from ledgercore.io import ensure_dir
from ledgercore.jsonio import dumps_json

from specmason.config import SpecMasonConfig
from specmason.coverage import CoverageReport, build_coverage, render_markdown
from specmason.errors import Finding, Findings
from specmason.evidence import (
    EvidenceReport,
    check_evidence_against_mappings,
    parse_junit_xml,
)
from specmason.gherkin.lint import lint_feature_with_authority
from specmason.gherkin.parser import GherkinParseError, parse_feature_file
from specmason.mappings import (
    MappingInventory,
    build_inventory,
    load_intentional_unmapped_policy,
)
from specmason.pytest_discovery import discover_tests
from specmason.requirements import RequirementsIndex


@dataclass(frozen=True)
class ReviewResult:
    """Outcome of a full review run."""

    config: SpecMasonConfig
    coverage: CoverageReport | None
    evidence: EvidenceReport | None
    mapping_inventory: MappingInventory
    findings: Findings
    reports_written: tuple[str, ...] = ()

    @property
    def has_errors(self) -> bool:
        return self.findings.has_errors

    def to_dict(self) -> dict[str, object]:
        return {
            "has_errors": self.has_errors,
            "findings": self.findings.to_list(),
            "coverage": self.coverage.to_dict() if self.coverage else None,
            "evidence": self.evidence.to_dict() if self.evidence else None,
            "reports_written": list(self.reports_written),
        }


def _load_features(cfg: SpecMasonConfig) -> tuple[list, Findings]:
    features: list = []
    findings = Findings()
    features_dir = cfg.features_dir
    if not features_dir.is_dir():
        return features, findings
    for path in sorted(features_dir.rglob("*.feature")):
        try:
            feature = parse_feature_file(path)
            features.append(feature)
        except GherkinParseError as exc:
            findings = findings.append(
                Finding(exc.code, "error", exc.message, exc.path or str(path))
            )
    return features, findings


def _check_features(
    features: list, cfg: SpecMasonConfig, index: RequirementsIndex | None
) -> Findings:
    findings = Findings()
    req_ids = index.requirement_ids if index else None
    ac_ids = index.criterion_ids if index else None
    for feature in features:
        findings = findings.extend(
            lint_feature_with_authority(
                feature,
                known_requirement_ids=req_ids,
                known_criterion_ids=ac_ids,
                require_req_tag=cfg.gherkin_require_req_tag,
                require_ac_tag=cfg.gherkin_require_ac_tag,
            )
        )
    return findings


def run_review(
    cfg: SpecMasonConfig,
    *,
    index: RequirementsIndex | None = None,
) -> ReviewResult:
    """Run the full review pipeline: check, coverage, evidence, write reports."""

    findings = Findings()
    reports_written: list[str] = []

    # Load features and check.
    features, load_findings = _load_features(cfg)
    findings = findings.extend(load_findings)

    # Lint features.
    check_findings = _check_features(features, cfg, index)
    findings = findings.extend(check_findings)

    # Load mapping policy and discover tests.
    central_waivers, policy_findings = load_intentional_unmapped_policy(
        cfg.pytest_intentional_unmapped_policy
    )
    findings = findings.extend(policy_findings)

    discovered = discover_tests(cfg.tests_dir, root=cfg.workspace_root)
    inventory = build_inventory(discovered, central_waivers=central_waivers)
    findings = findings.extend(inventory.findings)

    # Coverage.
    mode = cfg.mode
    coverage = build_coverage(features, inventory, index=index, mode=mode)
    findings = findings.extend(coverage.findings)

    # Evidence (optional).
    evidence_report: EvidenceReport | None = None
    evidence_dir = cfg.evidence_dir
    if evidence_dir.is_dir():
        for junit_path in sorted(evidence_dir.rglob("*.xml")):
            try:
                evidence_report = parse_junit_xml(junit_path)
                mapped_nodeids = {t.nodeid for t in inventory.tests if t.is_mapped}
                ev_findings = check_evidence_against_mappings(
                    evidence_report, mapped_nodeids
                )
                findings = findings.extend(ev_findings)
                break  # first XML found is sufficient for MVP
            except OSError as exc:
                findings = findings.append(
                    Finding(
                        "SML003",
                        "error",
                        f"failed to parse {junit_path}: {exc}",
                        str(junit_path),
                    )
                )

    # Write reports.
    ensure_dir(cfg.reports_state_dir)
    reports = {
        "coverage.md": render_markdown(coverage),
        "coverage.json": coverage.to_json(),
        "mappings.json": dumps_json(inventory.to_dict(), indent=2, sort_keys=True),
    }
    if evidence_report is not None:
        reports["evidence.json"] = dumps_json(
            evidence_report.to_dict(), indent=2, sort_keys=True
        )
    for filename, content in reports.items():
        path = cfg.reports_state_dir / filename
        atomic_write_text(path, content)
        reports_written.append(str(path))

    return ReviewResult(
        config=cfg,
        coverage=coverage,
        evidence=evidence_report,
        mapping_inventory=inventory,
        findings=findings,
        reports_written=tuple(reports_written),
    )


__all__ = ["ReviewResult", "run_review"]
