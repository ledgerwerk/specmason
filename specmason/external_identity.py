"""Stable external-corpus identity generation.

Generates deterministic scenario IDs for external Gherkin corpora that lack
``@req-REQ-NNNN`` / ``@ac-AC-NNNN`` tags. IDs are derived from the feature path,
rule context, scenario content, and examples-row values, so they remain stable
across line movement and distinguish repeated scenario titles with different
steps. They are written to ``manifest.json`` for downstream traceability.

Identity resolution order:

1. Explicit tag matching the configured namespace prefix (e.g. ``@EPUBCHECK-...``).
2. Deterministic hash: ``<NAMESPACE>-<8-char-upper-sha1(
       feature-relative-path + NUL + rule-name + NUL + scenario-signature
       + NUL + examples-row-key
   )>``.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from specmason.errors import SML003_INVALID_FEATURE_SYNTAX, Finding
from specmason.gherkin.model import (
    ExpandedScenario,
    Feature,
    Scenario,
    ScenarioOutline,
    Step,
    StepArgument,
    expand_scenarios,
)


@dataclass(frozen=True)
class IdentityItem:
    """A single identity mapping for a scenario or expanded outline example."""

    id: str
    feature: str
    scenario: str
    rule: str | None
    examples_row: dict[str, str] | None
    tags: tuple[str, ...]
    source_sha256: str


def _hash_key(
    feature_path: str,
    rule_name: str,
    scenario_signature: str,
    row_key: str,
) -> str:
    """Produce the 8-char upper SHA1 identity hash."""
    raw = f"{feature_path}\0{rule_name}\0{scenario_signature}\0{row_key}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:8].upper()


def _extract_explicit_id(tags: tuple[str, ...], namespace: str) -> str | None:
    """Return the first tag matching ``@<NAMESPACE>-...`` or ``None``."""
    prefix = f"@{namespace}-"
    for tag in tags:
        if tag.startswith(prefix):
            return tag[1:]  # strip leading @
    return None


def _row_key(expanded: ExpandedScenario) -> str:
    """Build a stable key from an examples row's column/value pairs."""
    block_key = f"{expanded.examples_index}:{expanded.examples_name}"
    parts = [f"{col}={val}" for col, val in expanded.row_values]
    return f"{block_key}|{'|'.join(parts)}"


def _step_argument_key(argument: StepArgument | None) -> str:
    if argument is None or argument.kind == "none":
        return ""
    if argument.kind == "docstring":
        return f"docstring:{argument.content_type}:{argument.content}"
    row_parts = ["|".join(cell.value for cell in row.cells) for row in argument.rows]
    return f"datatable:{'||'.join(row_parts)}"


def _step_key(step: Step) -> str:
    return "\0".join((step.keyword, step.text, _step_argument_key(step.argument)))


def _scenario_signature(scenario: Scenario | ScenarioOutline) -> str:
    tag_key = "|".join(scenario.tags)
    step_key = "\n".join(_step_key(step) for step in scenario.steps)
    return "\0".join((scenario.keyword, scenario.name, tag_key, step_key))


def _source_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _identity_for_scenario(
    scenario: Scenario | ScenarioOutline,
    *,
    feature_path: str,
    rule_name: str,
    namespace: str,
    feature_text: str,
) -> IdentityItem:
    """Generate an identity for a plain scenario (not expanded)."""
    explicit = _extract_explicit_id(scenario.tags, namespace)
    row_key = ""
    if explicit:
        item_id = explicit
    else:
        item_id = f"{namespace}-" + _hash_key(
            feature_path, rule_name, _scenario_signature(scenario), row_key
        )
    return IdentityItem(
        id=item_id,
        feature=feature_path,
        scenario=scenario.name,
        rule=rule_name or None,
        examples_row=None,
        tags=scenario.tags,
        source_sha256=_source_sha256(feature_text),
    )


def _identity_for_expanded(
    expanded: ExpandedScenario,
    *,
    namespace: str,
    feature_text: str,
) -> IdentityItem:
    """Generate an identity for an expanded outline example row."""
    outline = expanded.outline
    explicit = _extract_explicit_id(outline.tags, namespace)
    row_key = _row_key(expanded)
    if explicit:
        item_id = f"{explicit}-{expanded.outline_row_index}"
    else:
        item_id = f"{namespace}-" + _hash_key(
            expanded.feature_path,
            expanded.rule_name,
            _scenario_signature(outline),
            row_key,
        )
    row_dict = dict(expanded.row_values) if expanded.row_values else None

    return IdentityItem(
        id=item_id,
        feature=expanded.feature_path,
        scenario=outline.name,
        rule=expanded.rule_name or None,
        examples_row=row_dict,
        tags=outline.tags,
        source_sha256=_source_sha256(feature_text),
    )


@dataclass(frozen=True)
class IdentityManifest:
    """The identity manifest for an external Gherkin corpus."""

    schema_version: int
    namespace: str
    items: tuple[IdentityItem, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "namespace": self.namespace,
            "items": [
                {
                    "id": item.id,
                    "feature": item.feature,
                    "scenario": item.scenario,
                    "rule": item.rule,
                    "examples_row": item.examples_row,
                    "tags": list(item.tags),
                    "source_sha256": item.source_sha256,
                }
                for item in self.items
            ],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n"


def build_identity_manifest(
    features: list[Feature],
    *,
    namespace: str,
    feature_texts: dict[str, str] | None = None,
) -> tuple[IdentityManifest, list[Finding]]:
    """Build an identity manifest for all scenarios in *features*.

    Args:
        features: Parsed feature files.
        namespace: The ID namespace (e.g. ``"EPUBCHECK"``).
        feature_texts: Optional mapping of feature path → raw text for SHA256.
            When not provided, an empty string is hashed.

    Returns:
        A ``(manifest, findings)`` tuple.  Findings contain duplicate-ID errors.
    """
    if feature_texts is None:
        feature_texts = {}

    items: list[IdentityItem] = []
    seen_ids: dict[str, IdentityItem] = {}
    findings: list[Finding] = []

    for feature in features:
        path = feature.path
        text = feature_texts.get(path, "")

        # Top-level scenarios (not in outlines).
        for sc in feature.scenarios:
            item = _identity_for_scenario(
                sc,
                feature_path=path,
                rule_name="",
                namespace=namespace,
                feature_text=text,
            )
            items.append(item)

        # Top-level outlines: expand and identity each row.
        for outline in feature.outline_scenarios:
            expanded_rows = [
                e for e in expand_scenarios(feature) if e.outline is outline
            ]
            if expanded_rows:
                for expanded in expanded_rows:
                    item = _identity_for_expanded(
                        expanded, namespace=namespace, feature_text=text
                    )
                    items.append(item)
            else:
                # Outline with no examples: identity the outline itself.
                item = _identity_for_scenario(
                    outline,
                    feature_path=path,
                    rule_name="",
                    namespace=namespace,
                    feature_text=text,
                )
                items.append(item)

        # Rule-contained scenarios and outlines.
        for rule in feature.rules:
            for sc in rule.scenarios:
                item = _identity_for_scenario(
                    sc,
                    feature_path=path,
                    rule_name=rule.name,
                    namespace=namespace,
                    feature_text=text,
                )
                items.append(item)

            for outline in rule.outline_scenarios:
                expanded_rows = [
                    e
                    for e in expand_scenarios(feature)
                    if e.outline is outline and e.rule_name == rule.name
                ]
                if expanded_rows:
                    for expanded in expanded_rows:
                        item = _identity_for_expanded(
                            expanded,
                            namespace=namespace,
                            feature_text=text,
                        )
                        items.append(item)
                else:
                    item = _identity_for_scenario(
                        outline,
                        feature_path=path,
                        rule_name=rule.name,
                        namespace=namespace,
                        feature_text=text,
                    )
                    items.append(item)

    # Duplicate detection.
    for item in items:
        if item.id in seen_ids:
            existing = seen_ids[item.id]
            findings.append(
                Finding(
                    code=SML003_INVALID_FEATURE_SYNTAX,
                    severity="error",
                    message=(
                        f"Duplicate external identity '{item.id}': "
                        f"'{existing.feature}:{existing.scenario}' and "
                        f"'{item.feature}:{item.scenario}'"
                    ),
                    location=item.feature,
                )
            )
        else:
            seen_ids[item.id] = item

    manifest = IdentityManifest(
        schema_version=1,
        namespace=namespace,
        items=tuple(items),
    )
    return manifest, findings


def write_manifest(manifest: IdentityManifest, path: Path) -> None:
    """Write the manifest to *path* as deterministic JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(manifest.to_json(), encoding="utf-8")


__all__ = [
    "IdentityItem",
    "IdentityManifest",
    "build_identity_manifest",
    "write_manifest",
]
