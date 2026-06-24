"""Gherkin behavior-spec support for SpecMason.

This package supports the full Gherkin feature set: ``Feature``, ``Rule:``
blocks, ``Background:``, ``Scenario:``/``Example:``, ``Scenario Outline:``/
``Scenario Template:`` with ``Examples:`` tables, data tables, doc strings,
wildcard steps, ``# language`` headers, and comments.  The line-based parser
(``parse_feature``) handles the strict ReqLedger subset; the official parser
(``parse_feature_official``) handles the full corpus when the ``gherkin"
extra is installed.
"""

from __future__ import annotations

from specmason.gherkin.model import (
    Background,
    Comment,
    ExpandedScenario,
    ExamplesBlock,
    Feature,
    GherkinDocument,
    Rule,
    Scenario,
    ScenarioOutline,
    Step,
    StepArgument,
    StepOccurrence,
    StepPattern,
    TableCell,
    TableRow,
    expand_scenarios,
)
from specmason.gherkin.parser import (
    GherkinParseError,
    parse_feature,
    parse_feature_file,
)

# The official parser adapter is available only when the gherkin extra is
# installed.  Import lazily or guard at the call site.

__all__ = [
    "Background",
    "Comment",
    "ExpandedScenario",
    "ExamplesBlock",
    "Feature",
    "GherkinDocument",
    "GherkinParseError",
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
    "parse_feature",
    "parse_feature_file",
]
