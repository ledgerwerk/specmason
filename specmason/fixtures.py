"""Fixture reference extraction from Gherkin feature files.

Extracts candidate fixture references from quoted paths, ``files/`` tokens,
known suffixes, data-table cells, and doc strings.  Resolves them against
configured ``fixture_roots`` and reports whether each reference exists and its
kind (opf/xhtml/xml/css/epub/txt/dir/other).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from specmason.gherkin.model import (
    ExamplesBlock,
    Feature,
    Step,
)

_QUOTED_PATH_RE = re.compile(r'"([^"]*)"')
_FILES_TOKEN_RE = re.compile(r'(?:^|\s)(files/[^\s"\']+)')
_KNOWN_SUFFIXES: dict[str, str] = {
    ".epub": "epub",
    ".opf": "opf",
    ".xhtml": "xhtml",
    ".xml": "xml",
    ".css": "css",
    ".txt": "txt",
    ".html": "html",
}


@dataclass(frozen=True)
class FixtureRef:
    """A single extracted fixture reference with resolution metadata."""

    raw: str
    resolved: str
    exists: bool
    kind: str  # "opf", "xhtml", "xml", "css", "epub", "txt", "dir", "other"


def _classify_suffix(path: Path) -> str:
    suffix = path.suffix.lower()
    return _KNOWN_SUFFIXES.get(suffix, "dir" if path.is_dir() else "other")


def _resolve_candidate(
    raw: str, fixture_roots: tuple[Path, ...]
) -> tuple[str, bool, str]:
    """Resolve a raw fixture reference against fixture_roots.

    Returns (resolved_absolute_path_str, exists, kind).
    """
    for root in fixture_roots:
        candidate = (root / raw).resolve()
        if candidate.exists():
            return str(candidate), True, _classify_suffix(candidate)
    # Return the first root's resolution even if it doesn't exist.
    if fixture_roots:
        candidate = (fixture_roots[0] / raw).resolve()
        return str(candidate), False, _classify_suffix(candidate)
    return raw, False, "other"


def _extract_from_text(text: str) -> list[str]:
    """Extract candidate fixture references from free-form text."""
    refs: list[str] = []
    for m in _QUOTED_PATH_RE.finditer(text):
        val = m.group(1).strip()
        if val and ("/" in val or "\\" in val or "." in val):
            refs.append(val)
    for m in _FILES_TOKEN_RE.finditer(text):
        refs.append(m.group(1))
    return refs


def _looks_like_fixture(value: str) -> bool:
    """Return True if *value* looks like a bare fixture reference."""
    v = value.strip()
    if not v:
        return False
    if "/" in v or "\\" in v:
        return True
    for suffix in _KNOWN_SUFFIXES:
        if v.endswith(suffix):
            return True
    return False


def _extract_from_step(step: Step) -> list[str]:
    """Extract fixture references from a step's text and optional argument."""
    refs = _extract_from_text(step.text)
    if step.argument is not None:
        if step.argument.kind == "datatable":
            for row in step.argument.rows:
                for cell in row.cells:
                    if _looks_like_fixture(cell.value):
                        refs.append(cell.value.strip())
                    refs.extend(_extract_from_text(cell.value))
        elif step.argument.kind == "docstring":
            refs.extend(_extract_from_text(step.argument.content))
    return refs


def _dedup(refs: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for r in refs:
        if r not in seen:
            seen.add(r)
            result.append(r)
    return result


def _steps_from_feature(
    feature: Feature,
) -> list[tuple[str, Step, str]]:
    """Return (scenario_name, step, rule_name) triples."""
    triples: list[tuple[str, Step, str]] = []

    def _collect(steps: tuple[Step, ...], scenario_name: str, rule_name: str) -> None:
        for s in steps:
            triples.append((scenario_name, s, rule_name))

    if feature.background is not None:
        _collect(feature.background.steps, "<background>", "")

    for sc in feature.scenarios:
        _collect(sc.steps, sc.name, "")

    for outline in feature.outline_scenarios:
        _collect(outline.steps, outline.name, "")
        for block in outline.examples:
            _collect_examples(block)

    for rule in feature.rules:
        if rule.background is not None:
            _collect(rule.background.steps, "<background>", rule.name)
        for sc in rule.scenarios:
            _collect(sc.steps, sc.name, rule.name)
        for outline in rule.outline_scenarios:
            _collect(outline.steps, outline.name, rule.name)
            for block in outline.examples:
                _collect_examples(block)

    return triples


def _collect_examples(block: ExamplesBlock) -> None:
    """Extract fixtures from examples table cells."""
    # This is called separately; actual fixture extraction happens in
    # extract_fixture_refs which iterates examples blocks.


def _collect_steps(steps: tuple[Step, ...], raw_refs: list[str]) -> None:
    """Extend raw_refs with fixtures extracted from each step."""
    for step in steps:
        raw_refs.extend(_extract_from_step(step))


def _collect_examples_blocks(
    blocks: tuple[ExamplesBlock, ...], raw_refs: list[str]
) -> None:
    """Extend raw_refs with fixtures from examples table header cells."""
    for block in blocks:
        if block.header is None:
            continue
        for cell in block.header.cells:
            if _looks_like_fixture(cell.value):
                raw_refs.append(cell.value.strip())
            raw_refs.extend(_extract_from_text(cell.value))


def _collect_outlines(outlines, raw_refs: list[str]) -> None:
    """Extend raw_refs with fixtures from outline steps and examples tables."""
    for outline in outlines:
        _collect_steps(outline.steps, raw_refs)
        _collect_examples_blocks(outline.examples, raw_refs)


def _collect_rules(rules, raw_refs: list[str]) -> None:
    """Extend raw_refs with fixtures from rule backgrounds, scenarios, outlines."""
    for rule in rules:
        if rule.background is not None:
            _collect_steps(rule.background.steps, raw_refs)
        for sc in rule.scenarios:
            _collect_steps(sc.steps, raw_refs)
        _collect_outlines(rule.outline_scenarios, raw_refs)


def extract_fixture_refs(
    feature: Feature,
    fixture_roots: tuple[Path, ...],
) -> tuple[FixtureRef, ...]:
    """Extract and resolve all fixture references from a feature.

    Returns a deduplicated tuple of :class:`FixtureRef` objects.
    """
    raw_refs: list[str] = []

    if feature.background is not None:
        _collect_steps(feature.background.steps, raw_refs)
    for sc in feature.scenarios:
        _collect_steps(sc.steps, raw_refs)
    _collect_outlines(feature.outline_scenarios, raw_refs)
    _collect_rules(feature.rules, raw_refs)

    result: list[FixtureRef] = []
    for raw in _dedup(raw_refs):
        resolved, exists, kind = _resolve_candidate(raw, fixture_roots)
        result.append(FixtureRef(raw=raw, resolved=resolved, exists=exists, kind=kind))

    return tuple(sorted(result, key=lambda f: f.raw))


__all__ = [
    "FixtureRef",
    "extract_fixture_refs",
]
