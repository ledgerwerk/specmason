"""Deterministic ``.feature`` rendering and generation.

:func:`render_feature` round-trips a parsed :class:`Feature` back to stable text,
handling Background, Scenario Outline, Examples, data tables, doc strings,
and wildcard steps in addition to the classic Scenario/Rule subset.
:func:`build_feature_for_criterion` produces a draft feature for an accepted
behavior criterion, tagged ``@req-* @ac-* @needs-review`` with safe placeholder
steps (SML019). Output is byte-stable for a fixed input.
"""

from __future__ import annotations

from specmason.errors import (
    SML019_GENERATED_FEATURE_NEEDS_REVIEW,
)
from specmason.gherkin.model import (
    Background,
    ExamplesBlock,
    Feature,
    Scenario,
    ScenarioOutline,
    Step,
    StepArgument,
    TableRow,
)

_PLACEHOLDER_STEPS: tuple[Step, ...] = (
    Step("Given", "the system is in the required precondition", 0),
    Step("When", "the described behavior occurs", 0),
    Step("Then", "the acceptance criterion is satisfied", 0),
)


def _render_tags(tags: tuple[str, ...], indent: str) -> str | None:
    if not tags:
        return None
    return f"{indent}{' '.join(tags)}"


def _render_table_row(row: TableRow, indent: str) -> str:
    cells = " | ".join(c.value for c in row.cells)
    return f"{indent}| {cells} |"


def _render_argument(argument: StepArgument, indent: str) -> list[str]:
    """Render a step argument (data table or doc string)."""
    lines: list[str] = []
    if argument.kind == "datatable":
        for row in argument.rows:
            lines.append(_render_table_row(row, indent))
    elif argument.kind == "docstring":
        delimiter = '"""'
        media = f" {argument.content_type}" if argument.content_type else ""
        lines.append(f"{indent}{delimiter}{media}")
        for content_line in argument.content.splitlines():
            lines.append(f"{indent}{content_line}")
        lines.append(f"{indent}{delimiter}")
    return lines


def _render_step(step: Step, indent: str) -> list[str]:
    """Render a step with its optional argument."""
    lines: list[str] = []
    step_text = f"{indent}{step.keyword} {step.text}".rstrip()
    lines.append(step_text)
    if step.argument is not None:
        lines.extend(_render_argument(step.argument, indent))
    return lines


def _render_background(background: Background, indent: str) -> list[str]:
    """Render a Background block."""
    lines: list[str] = []
    name_part = f": {background.name}" if background.name else ""
    lines.append(f"{indent}Background:{name_part}".rstrip())
    inner = indent + "  "
    for step in background.steps:
        lines.extend(_render_step(step, inner))
    return lines


def _render_examples_block(block: ExamplesBlock, indent: str) -> list[str]:
    """Render an Examples block with its table."""
    lines: list[str] = []
    tag_line = _render_tags(block.tags, indent)
    if tag_line is not None:
        lines.append(tag_line)
    name_part = f": {block.name}" if block.name else ""
    lines.append(f"{indent}Examples:{name_part}".rstrip())
    if block.header is not None:
        lines.append(_render_table_row(block.header, indent + "  "))
    for row in block.body:
        lines.append(_render_table_row(row, indent + "  "))
    return lines


def _render_scenario(scenario: Scenario, indent: str) -> list[str]:
    """Render a Scenario block."""
    lines: list[str] = []
    tag_line = _render_tags(scenario.tags, indent)
    if tag_line is not None:
        lines.append(tag_line)
    lines.append(f"{indent}{scenario.keyword}: {scenario.name}".rstrip())
    if scenario.description:
        for desc_line in scenario.description.splitlines():
            lines.append(f"{indent}  {desc_line}")
    inner = indent + "  "
    for step in scenario.steps:
        lines.extend(_render_step(step, inner))
    return lines


def _render_outline(outline: ScenarioOutline, indent: str) -> list[str]:
    """Render a Scenario Outline block with its examples."""
    lines: list[str] = []
    tag_line = _render_tags(outline.tags, indent)
    if tag_line is not None:
        lines.append(tag_line)
    lines.append(f"{indent}{outline.keyword}: {outline.name}".rstrip())
    if outline.description:
        for desc_line in outline.description.splitlines():
            lines.append(f"{indent}  {desc_line}")
    inner = indent + "  "
    for step in outline.steps:
        lines.extend(_render_step(step, inner))
    for block in outline.examples:
        lines.append("")
        lines.extend(_render_examples_block(block, indent))
    return lines


def render_feature(feature: Feature) -> str:
    """Render a feature to deterministic text with a trailing newline."""
    lines: list[str] = []
    tag_line = _render_tags(feature.tags, "")
    if tag_line is not None:
        lines.append(tag_line)
    lines.append(f"Feature: {feature.name}".rstrip())
    if feature.description:
        lines.append(feature.description)

    if feature.background is not None:
        lines.append("")
        lines.extend(_render_background(feature.background, "  "))

    for scenario in feature.scenarios:
        lines.append("")
        lines.extend(_render_scenario(scenario, "  "))

    for outline in feature.outline_scenarios:
        lines.append("")
        lines.extend(_render_outline(outline, "  "))

    for rule in feature.rules:
        lines.append("")
        rule_tag = _render_tags(rule.tags, "  ")
        if rule_tag is not None:
            lines.append(rule_tag)
        lines.append(f"  Rule: {rule.name}".rstrip())
        if rule.description:
            lines.append(f"  {rule.description}")
        if rule.background is not None:
            lines.append("")
            lines.extend(_render_background(rule.background, "    "))
        for scenario in rule.scenarios:
            lines.append("")
            lines.extend(_render_scenario(scenario, "    "))
        for outline in rule.outline_scenarios:
            lines.append("")
            lines.extend(_render_outline(outline, "    "))

    return "\n".join(lines) + "\n"


def build_scenario_for_criterion(
    *,
    req_id: str,
    ac_id: str,
    statement: str,
    keyword: str = "Scenario",
) -> Scenario:
    """Build a draft scenario for an accepted behavior criterion."""
    return Scenario(
        keyword=keyword,
        name=statement,
        tags=(f"@req-{req_id}", f"@ac-{ac_id}", "@needs-review"),
        steps=_PLACEHOLDER_STEPS,
    )


def build_feature_for_criterion(
    *,
    req_id: str,
    ac_id: str,
    title: str,
    statement: str,
) -> Feature:
    """Build a draft single-scenario feature for an accepted criterion.

    Marked ``@needs-review`` because generated content must be reviewed before it
    can satisfy coverage (SML019 is informational).
    """
    scenario = build_scenario_for_criterion(
        req_id=req_id, ac_id=ac_id, statement=statement
    )
    return Feature(name=title, scenarios=(scenario,))


def feature_filename_for(req_id: str, ac_id: str, *, title: str = "") -> str:
    """Return a deterministic, unique ``.feature`` filename for a criterion.

    Always embeds both the requirement and criterion ids so that multiple
    criteria under one requirement cannot collide.
    """
    del title
    return f"{req_id.lower()}-{ac_id.lower()}.feature"


def needs_review_finding(feature: Feature) -> str | None:
    """Return SML019 info text if the feature is a generated draft."""
    for scenario in feature.iter_scenarios():
        if "@needs-review" in scenario.tags:
            return SML019_GENERATED_FEATURE_NEEDS_REVIEW
    return None


__all__ = [
    "build_feature_for_criterion",
    "build_scenario_for_criterion",
    "feature_filename_for",
    "needs_review_finding",
    "render_feature",
]
