"""Gherkin behavior-spec support for SpecMason.

This package implements the supported MVP subset of Gherkin (classic
``.feature`` files): ``Feature``, ``Rule``, ``Scenario``/``Example``,
``Given``/``When``/``Then``/``And``/``But`` steps, tags, comments, and
descriptions. Unsupported constructs (Background, Scenario Outline/Template,
Examples tables, data tables, doc strings, wildcard steps, multiple Feature
blocks per file, markdown-with-Gherkin) fail closed during ``check``.
"""

from __future__ import annotations

from specmason.gherkin.model import (
    Feature,
    Rule,
    Scenario,
    Step,
)
from specmason.gherkin.parser import (
    GherkinParseError,
    parse_feature,
    parse_feature_file,
)

__all__ = [
    "Feature",
    "GherkinParseError",
    "Rule",
    "Scenario",
    "Step",
    "parse_feature",
    "parse_feature_file",
]
