"""Dataclasses for the Gherkin model.

All models are frozen and preserve source line numbers for diagnostics.  The
classes here support both the strict ReqLedger subset (``@req-REQ-NNNN`` /
``@ac-AC-NNNN`` tags) and the richer constructs that appear in mature Cucumber
corpora (Background, Scenario Outline, Examples, data tables, doc strings,
wildcard steps, ``# language`` headers, comments).
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from specmason.errors import Finding


# ---------------------------------------------------------------------------
# Comment
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Comment:
    """A ``#`` comment line inside a Gherkin document."""

    text: str
    line: int


# ---------------------------------------------------------------------------
# Table and step-argument primitives
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TableCell:
    """A single cell in a data table or examples table row."""

    value: str
    line: int = 0


@dataclass(frozen=True)
class TableRow:
    """A row in a data table or examples table."""

    cells: tuple[TableCell, ...] = ()
    line: int = 0


@dataclass(frozen=True)
class StepArgument:
    """An optional argument attached to a step (data table or doc string).

    ``kind`` is ``'none'``, ``'datatable'``, or ``'docstring'``.
    """

    kind: Literal["none", "datatable", "docstring"] = "none"
    rows: tuple[TableRow, ...] = ()
    content: str = ""
    content_type: str = ""
    line: int = 0


# ---------------------------------------------------------------------------
# Background
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Background:
    """A ``Background:`` block with shared steps."""

    name: str
    steps: tuple[Step, ...] = ()
    line: int = 0


# ---------------------------------------------------------------------------
# Step
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Step:
    """A single Given/When/Then/And/But step."""

    keyword: str
    text: str
    line: int
    argument: StepArgument | None = None


# ---------------------------------------------------------------------------
# Scenario / Scenario Outline
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Scenario:
    """A ``Scenario:`` (or ``Example:``) block."""

    keyword: str
    name: str
    tags: tuple[str, ...]
    steps: tuple[Step, ...] = ()
    description: str = ""
    line: int = 0
    rule_name: str = ""


@dataclass(frozen=True)
class ExamplesBlock:
    """An ``Examples:`` table within a Scenario Outline.

    ``header`` is the first row (column names); ``body`` contains the data rows.
    """

    keyword: str
    name: str
    tags: tuple[str, ...] = ()
    header: TableRow | None = None
    body: tuple[TableRow, ...] = ()
    description: str = ""
    line: int = 0


@dataclass(frozen=True)
class ScenarioOutline:
    """A ``Scenario Outline:`` (or ``Scenario Template:``) block.

    Template parameters (e.g. ``<name>``) are substituted from the associated
    :class:`ExamplesBlock` rows during expansion.
    """

    keyword: str
    name: str
    tags: tuple[str, ...]
    steps: tuple[Step, ...] = ()
    examples: tuple[ExamplesBlock, ...] = ()
    description: str = ""
    line: int = 0
    rule_name: str = ""


# ---------------------------------------------------------------------------
# Rule
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Rule:
    """A ``Rule:`` block grouping scenarios."""

    name: str
    tags: tuple[str, ...] = ()
    description: str = ""
    scenarios: tuple[Scenario, ...] = ()
    outline_scenarios: tuple[ScenarioOutline, ...] = ()
    background: Background | None = None
    line: int = 0


# ---------------------------------------------------------------------------
# Feature
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Feature:
    """A parsed ``.feature`` document."""

    name: str
    tags: tuple[str, ...] = ()
    description: str = ""
    language: str = "en"
    scenarios: tuple[Scenario, ...] = ()
    outline_scenarios: tuple[ScenarioOutline, ...] = ()
    rules: tuple[Rule, ...] = ()
    background: Background | None = None
    path: str = ""
    line: int = 0
    extra: dict[str, object] = field(default_factory=dict)

    def iter_scenarios(self) -> Iterator[Scenario]:
        """Yield every Scenario (top-level and within rules)."""
        yield from self.scenarios
        for rule in self.rules:
            yield from rule.scenarios

    def iter_outlines(self) -> Iterator[ScenarioOutline]:
        """Yield every ScenarioOutline (top-level and within rules)."""
        yield from self.outline_scenarios
        for rule in self.rules:
            yield from rule.outline_scenarios

    @property
    def all_scenarios(self) -> tuple[Scenario, ...]:
        """Flat tuple of all Scenario blocks in the feature."""
        return tuple(self.iter_scenarios())

    @property
    def all_outlines(self) -> tuple[ScenarioOutline, ...]:
        """Flat tuple of all ScenarioOutline blocks in the feature."""
        return tuple(self.iter_outlines())


# ---------------------------------------------------------------------------
# Expanded scenario (outline + examples row)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExpandedScenario:
    """One concrete scenario expanded from a ScenarioOutline + one examples row.

    ``row_values`` contains ``(column_name, cell_value)`` pairs for
    substitution and identity generation.
    """

    outline: ScenarioOutline
    outline_row_index: int
    row_values: tuple[tuple[str, str], ...]
    feature_path: str = ""
    rule_name: str = ""
    examples_index: int = 0
    examples_name: str = ""


# ---------------------------------------------------------------------------
# Step vocabulary primitives
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StepOccurrence:
    """A single location where a normalized step pattern appears."""

    path: str
    scenario_name: str
    line: int


@dataclass(frozen=True)
class StepPattern:
    """A normalized step pattern with all its occurrences."""

    keyword: str
    normalized_text: str
    occurrences: tuple[StepOccurrence, ...] = ()


# ---------------------------------------------------------------------------
# Gherkin document wrapper
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GherkinDocument:
    """Top-level result of parsing a single ``.feature`` file.

    The official parser returns this wrapper; the line-based parser returns
    just the :class:`Feature` (comments and parse warnings are not collected).
    """

    path: str
    feature: Feature
    comments: tuple[Comment, ...] = ()
    parse_warnings: tuple[Finding, ...] = ()


# ---------------------------------------------------------------------------
# Expansion helper
# ---------------------------------------------------------------------------


def expand_scenarios(feature: Feature) -> tuple[ExpandedScenario, ...]:
    """Expand every ScenarioOutline in *feature* against its Examples rows.

    Returns one :class:`ExpandedScenario` per (outline, examples-block, row)
    combination.  When an outline has no Examples block or the header is
    missing, the outline itself is skipped (no expansion is produced).
    """
    result: list[ExpandedScenario] = []
    path = feature.path

    def _expand(
        outline: ScenarioOutline, *, rule_name: str
    ) -> Iterator[ExpandedScenario]:
        for block_index, block in enumerate(outline.examples):
            if block.header is None:
                continue
            headers = [c.value for c in block.header.cells]
            for idx, row in enumerate(block.body):
                values = tuple(zip(headers, (c.value for c in row.cells), strict=True))
                yield ExpandedScenario(
                    outline=outline,
                    examples_index=block_index,
                    examples_name=block.name,
                    outline_row_index=idx,
                    row_values=values,
                    feature_path=path,
                    rule_name=rule_name,
                )

    for outline in feature.outline_scenarios:
        result.extend(_expand(outline, rule_name=""))

    for rule in feature.rules:
        for outline in rule.outline_scenarios:
            result.extend(_expand(outline, rule_name=rule.name))

    return tuple(result)


__all__ = [
    "Background",
    "Comment",
    "ExpandedScenario",
    "ExamplesBlock",
    "Feature",
    "GherkinDocument",
    "Rule",
    "Scenario",
    "ScenarioOutline",
    "Step",
    "StepArgument",
    "StepOccurrence",
    "StepPattern",
    "TableCell",
    "TableRow",
    "expand_scenarios",
]
