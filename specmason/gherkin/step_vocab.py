"""Step normalization and vocabulary grouping.

Normalizes Gherkin step text for grouping:

- Lowercase everything outside quoted strings.
- Quoted strings → ``{string}``.
- Integers → ``{int}``.
- Fixture-looking paths (containing ``/`` and a known suffix) → ``{path}``.
- Retain the original keyword (Given/When/Then/And/But/*).
"""

from __future__ import annotations

import re
from collections import defaultdict

from specmason.gherkin.model import (
    Feature,
    Step,
    StepOccurrence,
    StepPattern,
)

_QUOTED_RE = re.compile(r'"[^"]*"')
_INT_RE = re.compile(r"\b\d+\b")
_FIXTURE_SUFFIXES = (".epub", ".opf", ".xhtml", ".xml", ".css", ".txt", ".html")
_FIXTURE_RE = re.compile(
    r"(?:^|(?<=[\s(]))"  # start or preceded by space/paren
    r"[\w./\\-]*" + "(?:" + "|".join(re.escape(s) for s in _FIXTURE_SUFFIXES) + ")"
    r"(?:\b|$)"
)


def normalize_step_text(text: str) -> str:
    """Normalize step text for vocabulary grouping.

    Lowercase text outside quotes; replace quoted strings with ``{string}``,
    integers with ``{int}``, and fixture-looking paths with ``{path}``.
    """
    # Protect quoted strings first.
    placeholders: list[str] = []
    counter = 0

    def _replace_quoted(match: re.Match[str]) -> str:
        nonlocal counter
        key = f"__strph{counter}__"
        placeholders.append(key)
        counter += 1
        return key

    result = _QUOTED_RE.sub(_replace_quoted, text)

    # Replace integers.
    result = _INT_RE.sub("{int}", result)

    # Replace fixture-looking paths.
    result = _FIXTURE_RE.sub("{path}", result)

    # Lowercase everything.
    result = result.lower()

    # Restore placeholders as {string}.
    for key in placeholders:
        result = result.replace(key, "{string}")

    return result.strip()


def _steps_from_feature(feature: Feature) -> list[tuple[str, Step, str]]:
    """Return ``(path, step, scenario_name)`` triples from a feature."""
    pairs: list[tuple[str, Step, str]] = []
    path = feature.path

    def _collect_steps(
        steps: tuple[Step, ...], scenario_name: str
    ) -> list[tuple[str, Step, str]]:
        return [(path, s, scenario_name) for s in steps]

    if feature.background is not None:
        pairs.extend(_collect_steps(feature.background.steps, "<background>"))

    for sc in feature.scenarios:
        pairs.extend(_collect_steps(sc.steps, sc.name))

    for outline in feature.outline_scenarios:
        pairs.extend(_collect_steps(outline.steps, outline.name))

    for rule in feature.rules:
        if rule.background is not None:
            pairs.extend(
                _collect_steps(rule.background.steps, f"{rule.name}/<background>")
            )
        for sc in rule.scenarios:
            pairs.extend(_collect_steps(sc.steps, sc.name))
        for outline in rule.outline_scenarios:
            pairs.extend(_collect_steps(outline.steps, outline.name))

    return pairs


def build_step_vocabulary(
    features: list[Feature],
) -> tuple[StepPattern, ...]:
    """Group all steps from *features* by normalized pattern.

    Returns a sorted tuple of :class:`StepPattern` objects, each containing
    all :class:`StepOccurrence` locations where that pattern appears.
    """
    groups: dict[tuple[str, str], list[StepOccurrence]] = defaultdict(list)

    for feature in features:
        for path, step, scenario_name in _steps_from_feature(feature):
            normalized = normalize_step_text(step.text)
            key = (step.keyword, normalized)
            groups[key].append(
                StepOccurrence(
                    path=path,
                    scenario_name=scenario_name,
                    line=step.line,
                )
            )

    patterns: list[StepPattern] = []
    for (keyword, normalized), occurrences in sorted(groups.items()):
        patterns.append(
            StepPattern(
                keyword=keyword,
                normalized_text=normalized,
                occurrences=tuple(sorted(occurrences, key=lambda o: (o.path, o.line))),
            )
        )

    return tuple(sorted(patterns, key=lambda p: (p.keyword, p.normalized_text)))


__all__ = [
    "build_step_vocabulary",
    "normalize_step_text",
]
