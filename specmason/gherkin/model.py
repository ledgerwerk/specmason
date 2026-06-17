"""Dataclasses for the supported Gherkin subset.

All models are frozen and preserve source line numbers for diagnostics. IDs are
the binding authority (via ``@req-REQ-NNNN`` / ``@ac-AC-NNNN`` tags); titles are
never identity.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Step:
    """A single Given/When/Then/And/But step."""

    keyword: str
    text: str
    line: int


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
class Rule:
    """A ``Rule:`` block grouping scenarios."""

    name: str
    tags: tuple[str, ...] = ()
    description: str = ""
    scenarios: tuple[Scenario, ...] = ()
    line: int = 0


@dataclass(frozen=True)
class Feature:
    """A parsed ``.feature`` document (exactly one Feature per file in MVP)."""

    name: str
    tags: tuple[str, ...] = ()
    description: str = ""
    language: str = "en"
    scenarios: tuple[Scenario, ...] = ()
    rules: tuple[Rule, ...] = ()
    path: str = ""
    line: int = 0
    extra: dict[str, object] = field(default_factory=dict)

    def iter_scenarios(self) -> Iterator[Scenario]:
        """Yield every scenario (top-level and within rules)."""
        yield from self.scenarios
        for rule in self.rules:
            yield from rule.scenarios

    @property
    def all_scenarios(self) -> tuple[Scenario, ...]:
        """Flat tuple of all scenarios in the feature."""
        return tuple(self.iter_scenarios())


__all__ = [
    "Feature",
    "Rule",
    "Scenario",
    "Step",
]
