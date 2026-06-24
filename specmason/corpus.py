"""External corpus inventory and reporting.

Orchestrates Gherkin parsing, scenario-outline expansion, step vocabulary
building, fixture extraction, and identity generation for an external corpus.
Provides deterministic JSON/Markdown reports for:

- ``corpus inspect``: feature/scenario/outline/step/tag/fixture/finding counts.
- ``corpus steps``: normalized step vocabulary with occurrence counts.
- ``corpus fixtures``: extracted fixture references with resolution metadata.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from specmason.errors import Finding
from specmason.external_identity import (
    IdentityManifest,
    build_identity_manifest,
)
from specmason.fixtures import extract_fixture_refs
from specmason.gherkin.model import (
    Feature,
    GherkinDocument,
    expand_scenarios,
)
from specmason.gherkin.parser import GherkinParseError
from specmason.gherkin.step_vocab import StepPattern, build_step_vocabulary

# ---------------------------------------------------------------------------
# Corpus parsing
# ---------------------------------------------------------------------------


def parse_corpus(
    features_dir: Path,
    *,
    official_parser: bool,
) -> tuple[list[Feature], list[GherkinDocument], list[Finding]]:
    """Parse all .feature files under *features_dir*.

    Returns (features, documents, findings).  When *official_parser* is True,
    uses gherkin-official; otherwise uses the line-based parser.
    """
    features: list[Feature] = []
    documents: list[GherkinDocument] = []
    findings: list[Finding] = []

    if not features_dir.is_dir():
        findings.append(
            Finding(
                code="SML024",
                severity="error",
                message=f"Features directory not found: {features_dir}",
                location=str(features_dir),
            )
        )
        return features, documents, findings

    for path in sorted(features_dir.rglob("*.feature")):
        try:
            if official_parser:
                from specmason.gherkin.official import (
                    parse_document_official,
                )

                doc = parse_document_official(
                    path.read_text(encoding="utf-8"), path=str(path)
                )
                features.append(doc.feature)
                documents.append(doc)
            else:
                from specmason.gherkin.parser import parse_feature_file

                feat = parse_feature_file(path)
                features.append(feat)
        except GherkinParseError as exc:
            findings.append(
                Finding(
                    code=exc.code,
                    severity="error",
                    message=exc.message,
                    location=f"{exc.path}:{exc.line}" if exc.path else "",
                )
            )

    return features, documents, findings


# ---------------------------------------------------------------------------
# Corpus inventory
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CorpusInventory:
    """Structured inventory of an external Gherkin corpus."""

    feature_count: int
    scenario_count: int
    outline_count: int
    expanded_example_count: int
    step_pattern_count: int
    step_count: int
    tag_count: int
    fixture_ref_count: int
    findings: tuple[Finding, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "feature_count": self.feature_count,
            "scenario_count": self.scenario_count,
            "outline_count": self.outline_count,
            "expanded_example_count": self.expanded_example_count,
            "step_pattern_count": self.step_pattern_count,
            "step_count": self.step_count,
            "tag_count": self.tag_count,
            "fixture_ref_count": self.fixture_ref_count,
            "findings": [f.to_dict() for f in self.findings],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n"


def build_corpus_inventory(
    features: list[Feature],
    findings: list[Finding],
    fixture_roots: tuple[Path, ...],
) -> CorpusInventory:
    """Build a corpus inventory from parsed features."""
    all_scenarios = sum(len(f.all_scenarios) for f in features)
    all_outlines = sum(len(f.all_outlines) for f in features)
    all_expanded = sum(len(expand_scenarios(f)) for f in features)

    vocab = build_step_vocabulary(features)
    step_pattern_count = len(vocab)
    step_count = sum(len(p.occurrences) for p in vocab)

    all_tags: set[str] = set()
    for feat in features:
        all_tags.update(feat.tags)
        for sc in feat.all_scenarios:
            all_tags.update(sc.tags)
        for ol in feat.all_outlines:
            all_tags.update(ol.tags)
            for block in ol.examples:
                all_tags.update(block.tags)
        for rule in feat.rules:
            all_tags.update(rule.tags)

    fixture_count = 0
    for feat in features:
        fixture_count += len(extract_fixture_refs(feat, fixture_roots))

    return CorpusInventory(
        feature_count=len(features),
        scenario_count=all_scenarios,
        outline_count=all_outlines,
        expanded_example_count=all_expanded,
        step_pattern_count=step_pattern_count,
        step_count=step_count,
        tag_count=len(all_tags),
        fixture_ref_count=fixture_count,
        findings=tuple(findings),
    )


# ---------------------------------------------------------------------------
# Steps report
# ---------------------------------------------------------------------------


def render_steps_markdown(vocab: tuple[StepPattern, ...]) -> str:
    """Render the step vocabulary as deterministic Markdown."""
    lines: list[str] = ["# Step Vocabulary", ""]
    lines.append(f"**{len(vocab)}** unique normalized step patterns.\n")
    lines.append("| # | Keyword | Normalized text | Occurrences |")
    lines.append("|---:|---------|-----------------|------------:|")
    for i, pattern in enumerate(vocab, 1):
        lines.append(
            f"| {i} | {pattern.keyword} | {pattern.normalized_text} "
            f"| {len(pattern.occurrences)} |"
        )
    lines.append("")
    return "\n".join(lines) + "\n"


def render_steps_json(vocab: tuple[StepPattern, ...]) -> str:
    """Render the step vocabulary as deterministic JSON."""
    data = {
        "pattern_count": len(vocab),
        "patterns": [
            {
                "keyword": p.keyword,
                "normalized_text": p.normalized_text,
                "occurrence_count": len(p.occurrences),
                "occurrences": [
                    {
                        "path": o.path,
                        "scenario_name": o.scenario_name,
                        "line": o.line,
                    }
                    for o in p.occurrences
                ],
            }
            for p in vocab
        ],
    }
    return json.dumps(data, indent=2, sort_keys=True) + "\n"


# ---------------------------------------------------------------------------
# Fixtures report
# ---------------------------------------------------------------------------


def render_fixtures_json(
    features: list[Feature],
    fixture_roots: tuple[Path, ...],
) -> str:
    """Render fixture references as deterministic JSON."""
    all_refs: list[dict[str, Any]] = []
    for feat in features:
        for ref in extract_fixture_refs(feat, fixture_roots):
            all_refs.append(
                {
                    "feature": feat.path,
                    "raw": ref.raw,
                    "resolved": ref.resolved,
                    "exists": ref.exists,
                    "kind": ref.kind,
                }
            )
    data = {
        "fixture_ref_count": len(all_refs),
        "refs": sorted(all_refs, key=lambda r: (r["feature"], r["raw"])),
    }
    return json.dumps(data, indent=2, sort_keys=True) + "\n"


# ---------------------------------------------------------------------------
# High-level entry points (used by CLI)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CorpusInspectResult:
    """Result of a corpus inspect run."""

    inventory: CorpusInventory
    identity: IdentityManifest | None
    identity_findings: tuple[Finding, ...]

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = self.inventory.to_dict()
        if self.identity is not None:
            result["identity"] = {
                "namespace": self.identity.namespace,
                "item_count": len(self.identity.items),
            }
        if self.identity_findings:
            result["identity_findings"] = [f.to_dict() for f in self.identity_findings]
        return result

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n"


def run_corpus_inspect(
    features_dir: Path,
    *,
    official_parser: bool,
    fixture_roots: tuple[Path, ...],
    namespace: str = "",
) -> tuple[CorpusInspectResult, list[Finding]]:
    """Run a full corpus inspection.

    Returns (result, all_findings).
    """
    features, documents, parse_findings = parse_corpus(
        features_dir, official_parser=official_parser
    )

    inventory = build_corpus_inventory(features, parse_findings, fixture_roots)

    identity: IdentityManifest | None = None
    identity_findings: list[Finding] = []
    if namespace:
        feature_texts: dict[str, str] = {}
        for doc in documents:
            path = Path(doc.path)
            if path.is_file():
                feature_texts[doc.path] = path.read_text(encoding="utf-8")
        identity, identity_findings = build_identity_manifest(
            features, namespace=namespace, feature_texts=feature_texts
        )

    all_findings = list(parse_findings) + list(identity_findings)

    result = CorpusInspectResult(
        inventory=inventory,
        identity=identity,
        identity_findings=tuple(identity_findings),
    )
    return result, all_findings


__all__ = [
    "CorpusInspectResult",
    "CorpusInventory",
    "build_corpus_inventory",
    "parse_corpus",
    "render_fixtures_json",
    "render_steps_json",
    "render_steps_markdown",
    "run_corpus_inspect",
]
