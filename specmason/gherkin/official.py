"""Adapter around the ``gherkin-official`` Python package.

Maps the gherkin-official dict AST into SpecMason frozen dataclasses, preserving
line numbers for diagnostics.  When ``gherkin-official`` is not installed,
import-time succeeds but parse calls raise :class:`GherkinParseError` with a
clear instruction to install the ``gherkin`` extra.
"""

from __future__ import annotations

from typing import Any

from specmason.errors import SML003_INVALID_FEATURE_SYNTAX
from specmason.gherkin.model import (
    Background,
    Comment,
    ExamplesBlock,
    Feature,
    GherkinDocument,
    Rule,
    Scenario,
    ScenarioOutline,
    Step,
    StepArgument,
    TableCell,
    TableRow,
)

# Import gherkin-official at module level; the guard lives in parse functions.
try:
    from gherkin.parser import Parser as _GherkinParser
    from gherkin.token_scanner import TokenScanner as _TokenScanner

    _HAS_GHERKIN = True
except ImportError:
    _HAS_GHERKIN = False

from specmason.gherkin.parser import GherkinParseError


def _require_gherkin() -> None:
    """Fail closed when the gherkin-official extra is missing."""
    if not _HAS_GHERKIN:
        raise GherkinParseError(
            SML003_INVALID_FEATURE_SYNTAX,
            "The gherkin-official package is not installed. "
            "Install the gherkin extra: pip install specmason[gherkin]",
            line=0,
            path="",
        )


def _loc(obj: dict[str, Any], key: str = "location") -> int:
    """Extract a 1-indexed line number from a gherkin-official location dict."""
    loc = obj.get(key, {})
    return int(loc.get("line", 0))


def _map_tags(tags: list[dict[str, Any]]) -> tuple[str, ...]:
    return tuple(t.get("name", "") for t in tags)


def _map_cell(cell: dict[str, Any]) -> TableCell:
    return TableCell(value=cell.get("value", ""), line=_loc(cell))


def _map_table_row(row: dict[str, Any]) -> TableRow:
    return TableRow(
        cells=tuple(_map_cell(c) for c in row.get("cells", [])),
        line=_loc(row),
    )


def _map_data_table(dt: dict[str, Any]) -> StepArgument:
    return StepArgument(
        kind="datatable",
        rows=tuple(_map_table_row(r) for r in dt.get("rows", [])),
        line=_loc(dt),
    )


def _map_doc_string(ds: dict[str, Any]) -> StepArgument:
    return StepArgument(
        kind="docstring",
        content=ds.get("content", ""),
        content_type=ds.get("mediaType", ""),
        line=_loc(ds),
    )


def _map_step(step: dict[str, Any]) -> Step:
    arg: StepArgument | None = None
    if "dataTable" in step:
        arg = _map_data_table(step["dataTable"])
    elif "docString" in step:
        arg = _map_doc_string(step["docString"])
    return Step(
        keyword=step.get("keyword", "").strip(),
        text=step.get("text", ""),
        line=_loc(step),
        argument=arg,
    )


def _map_background(bg: dict[str, Any]) -> Background:
    return Background(
        name=bg.get("name", ""),
        steps=tuple(_map_step(s) for s in bg.get("steps", [])),
        line=_loc(bg),
    )


def _map_examples(ex: dict[str, Any]) -> ExamplesBlock:
    header: TableRow | None = None
    body: tuple[TableRow, ...] = ()
    if "tableHeader" in ex:
        header = _map_table_row(ex["tableHeader"])
    body = tuple(_map_table_row(r) for r in ex.get("tableBody", []))
    return ExamplesBlock(
        keyword=ex.get("keyword", "Examples"),
        name=ex.get("name", ""),
        tags=_map_tags(ex.get("tags", [])),
        header=header,
        body=body,
        description=ex.get("description", "").strip(),
        line=_loc(ex),
    )


def _map_scenario(sc: dict[str, Any], *, rule_name: str) -> Scenario | ScenarioOutline:
    """Map a gherkin-official Scenario dict to Scenario or ScenarioOutline."""
    keyword = sc.get("keyword", "Scenario")
    tags = _map_tags(sc.get("tags", []))
    steps = tuple(_map_step(s) for s in sc.get("steps", []))
    desc = sc.get("description", "").strip()
    line = _loc(sc)
    examples = tuple(_map_examples(e) for e in sc.get("examples", []))

    if keyword in ("Scenario Outline", "Scenario Template"):
        return ScenarioOutline(
            keyword=keyword,
            name=sc.get("name", ""),
            tags=tags,
            steps=steps,
            examples=examples,
            description=desc,
            line=line,
            rule_name=rule_name,
        )
    return Scenario(
        keyword=keyword,
        name=sc.get("name", ""),
        tags=tags,
        steps=steps,
        description=desc,
        line=line,
        rule_name=rule_name,
    )


def _map_rule(rule: dict[str, Any]) -> Rule:
    """Map a gherkin-official Rule dict (with nested children)."""
    name = rule.get("name", "")
    tags = _map_tags(rule.get("tags", []))
    desc = rule.get("description", "").strip()
    line = _loc(rule)

    scenarios: list[Scenario] = []
    outlines: list[ScenarioOutline] = []
    bg: Background | None = None

    for child in rule.get("children", []):
        if "background" in child:
            bg = _map_background(child["background"])
        if "scenario" in child:
            mapped = _map_scenario(child["scenario"], rule_name=name)
            if isinstance(mapped, ScenarioOutline):
                outlines.append(mapped)
            else:
                scenarios.append(mapped)

    return Rule(
        name=name,
        tags=tags,
        description=desc,
        scenarios=tuple(scenarios),
        outline_scenarios=tuple(outlines),
        background=bg,
        line=line,
    )


def _map_feature(doc: dict[str, Any]) -> Feature:
    """Map the top-level ``feature`` dict from a gherkin-official document."""
    feat = doc.get("feature", {})
    name = feat.get("name", "")
    tags = _map_tags(feat.get("tags", []))
    desc = feat.get("description", "").strip()
    lang = feat.get("language", "en")
    line = _loc(feat)

    top_scenarios: list[Scenario] = []
    top_outlines: list[ScenarioOutline] = []
    rules: list[Rule] = []
    bg: Background | None = None

    for child in feat.get("children", []):
        if "background" in child:
            bg = _map_background(child["background"])
        if "scenario" in child:
            mapped = _map_scenario(child["scenario"], rule_name="")
            if isinstance(mapped, ScenarioOutline):
                top_outlines.append(mapped)
            else:
                top_scenarios.append(mapped)
        if "rule" in child:
            rules.append(_map_rule(child["rule"]))

    return Feature(
        name=name,
        tags=tags,
        description=desc,
        language=lang,
        scenarios=tuple(top_scenarios),
        outline_scenarios=tuple(top_outlines),
        rules=tuple(rules),
        background=bg,
        path="",
        line=line,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_feature_official(text: str, *, path: str = "") -> Feature:
    """Parse *text* with ``gherkin-official`` and return a :class:`Feature`.

    Raises :class:`GherkinParseError` (SML003) when the extra is missing or
    the document is syntactically invalid.
    """
    _require_gherkin()
    try:
        doc: dict[str, Any] = _GherkinParser().parse(_TokenScanner(text))
    except Exception as exc:
        raise GherkinParseError(
            SML003_INVALID_FEATURE_SYNTAX,
            str(exc),
            line=0,
            path=path,
        ) from exc
    feature = _map_feature(doc)
    if path:
        from dataclasses import replace

        feature = replace(feature, path=path)
    return feature


def parse_document_official(text: str, *, path: str = "") -> GherkinDocument:
    """Parse *text* with ``gherkin-official`` and return a :class:`GherkinDocument`.

    This variant also collects comments and exposes them alongside the feature.
    """
    _require_gherkin()
    try:
        doc: dict[str, Any] = _GherkinParser().parse(_TokenScanner(text))
    except Exception as exc:
        raise GherkinParseError(
            SML003_INVALID_FEATURE_SYNTAX,
            str(exc),
            line=0,
            path=path,
        ) from exc
    comments = tuple(
        Comment(text=c.get("text", ""), line=_loc(c)) for c in doc.get("comments", [])
    )
    feature = _map_feature(doc)
    if path:
        from dataclasses import replace

        feature = replace(feature, path=path)
    return GherkinDocument(path=path, feature=feature, comments=comments)


__all__ = [
    "parse_document_official",
    "parse_feature_official",
]
