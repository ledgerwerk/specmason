"""Line-based parser for the supported Gherkin subset.

Parses classic ``.feature`` files. Unsupported constructs fail closed with
:class:`GherkinParseError` carrying an SML code (``SML003`` invalid syntax or
``SML004`` unsupported construct) and a source line number.

File reading uses :func:`ledgercore.io.read_text`. Parsing is implemented as a
small state machine (``_FeatureParser``) so per-construct handling stays under
moderate complexity.
"""

from __future__ import annotations

import re
from dataclasses import replace
from pathlib import Path

from ledgercore.io import read_text

from specmason.errors import (
    SML003_INVALID_FEATURE_SYNTAX,
    SML004_UNSUPPORTED_GHERKIN_CONSTRUCT,
    SpecMasonError,
)
from specmason.gherkin.model import Feature, Rule, Scenario, Step

_FEATURE_RE = re.compile(r"^Feature:\s*(?P<name>.*)$")
_RULE_RE = re.compile(r"^Rule:\s*(?P<name>.*)$")
_SCENARIO_RE = re.compile(r"^(?P<kw>Scenario|Example):\s*(?P<name>.*)$")
_BACKGROUND_RE = re.compile(r"^Background:")
_OUTLINE_RE = re.compile(r"^Scenario\s+(?:Outline|Template):")
_EXAMPLES_RE = re.compile(r"^Examples:")
_STEP_RE = re.compile(r"^(?P<kw>Given|When|Then|And|But)(?:\s+(?P<text>.*))?$")
_WILDCARD_RE = re.compile(r"^\*\s+")
_TAG_RE = re.compile(r"^@")
_TAG_TOKEN_RE = re.compile(r"@[^\s]+")
_DOCSTRING_RE = re.compile(r'^("""|```)')

_MARKDOWN_SUFFIXES = (".md", ".markdown")


class GherkinParseError(SpecMasonError):
    """Raised when a feature file cannot be parsed in the supported subset."""

    def __init__(
        self, code: str, message: str, *, line: int = 0, path: str = ""
    ) -> None:
        self.code = code
        self.message = message
        self.line = line
        self.path = path
        location = f"{path}:{line}: " if path or line else ""
        super().__init__(f"{location}{code}: {message}")


def _unsupported(message: str, *, line: int, path: str) -> GherkinParseError:
    return GherkinParseError(
        SML004_UNSUPPORTED_GHERKIN_CONSTRUCT, message, line=line, path=path
    )


def _syntax(message: str, *, line: int, path: str) -> GherkinParseError:
    return GherkinParseError(
        SML003_INVALID_FEATURE_SYNTAX, message, line=line, path=path
    )


def _parse_tags(stripped: str) -> list[str]:
    return _TAG_TOKEN_RE.findall(stripped)


class _FeatureParser:
    """Mutable parse state for a single feature document."""

    def __init__(self, *, path: str) -> None:
        self.path = path
        self.feature: Feature | None = None
        self.current_rule_index: int | None = None
        self.pending_tags: list[str] = []
        self.feature_description: list[str] = []
        self.rule_descriptions: dict[int, list[str]] = {}
        self.scenario_description: list[str] = []
        self.top_scenarios: list[Scenario] = []
        self.rules_list: list[Rule] = []
        self.rule_scenarios: dict[int, list[Scenario]] = {}
        self.scenario: Scenario | None = None

    def parse(self, text: str) -> Feature:
        for index, raw in enumerate(text.splitlines(), start=1):
            stripped = raw.strip()
            if not stripped or stripped.startswith("#"):
                continue
            self._process_line(index, stripped)
        return self._finalize()

    def _process_line(self, index: int, stripped: str) -> None:
        if _DOCSTRING_RE.match(stripped):
            raise _unsupported(
                "doc strings are not supported in the MVP", line=index, path=self.path
            )
        if _TAG_RE.match(stripped):
            self.pending_tags.extend(_parse_tags(stripped))
            return
        if self._is_unsupported_block(stripped, index):
            return
        if self._handle_feature(index, stripped):
            return
        if self._handle_rule(index, stripped):
            return
        if self._handle_scenario(index, stripped):
            return
        if _WILDCARD_RE.match(stripped):
            raise _unsupported(
                "wildcard (*) steps are not supported in the MVP",
                line=index,
                path=self.path,
            )
        if stripped.startswith("|"):
            raise _unsupported(
                "data tables are not supported in the MVP", line=index, path=self.path
            )
        if self._handle_step(index, stripped):
            return
        self._handle_description(stripped)

    def _is_unsupported_block(self, stripped: str, index: int) -> bool:
        if _OUTLINE_RE.match(stripped):
            raise _unsupported(
                "Scenario Outline/Template is not supported in the MVP",
                line=index,
                path=self.path,
            )
        if _BACKGROUND_RE.match(stripped):
            raise _unsupported(
                "Background is not supported in the MVP", line=index, path=self.path
            )
        if _EXAMPLES_RE.match(stripped):
            raise _unsupported(
                "Examples tables are not supported in the MVP",
                line=index,
                path=self.path,
            )
        return False

    def _handle_feature(self, index: int, stripped: str) -> bool:
        m = _FEATURE_RE.match(stripped)
        if m is None:
            return False
        if self.feature is not None:
            raise _unsupported(
                "multiple Feature blocks per file are not supported in the MVP",
                line=index,
                path=self.path,
            )
        self.feature = Feature(
            name=m.group("name").strip(),
            tags=tuple(self.pending_tags),
            path=self.path,
            line=index,
        )
        self.pending_tags = []
        self.current_rule_index = None
        self.scenario = None
        return True

    def _handle_rule(self, index: int, stripped: str) -> bool:
        m = _RULE_RE.match(stripped)
        if m is None:
            return False
        if self.feature is None:
            raise _syntax("Rule before Feature", line=index, path=self.path)
        self._flush_scenario()
        idx = len(self.rules_list)
        self.rules_list.append(
            Rule(
                name=m.group("name").strip(),
                tags=tuple(self.pending_tags),
                line=index,
            )
        )
        self.rule_scenarios[idx] = []
        self.rule_descriptions[idx] = []
        self.current_rule_index = idx
        self.pending_tags = []
        self.scenario = None
        return True

    def _handle_scenario(self, index: int, stripped: str) -> bool:
        m = _SCENARIO_RE.match(stripped)
        if m is None:
            return False
        if self.feature is None:
            raise _syntax("Scenario before Feature", line=index, path=self.path)
        self._flush_scenario()
        rule_name = ""
        if self.current_rule_index is not None:
            rule_name = self.rules_list[self.current_rule_index].name
        self.scenario = Scenario(
            keyword=m.group("kw"),
            name=m.group("name").strip(),
            tags=tuple(self.pending_tags),
            line=index,
            rule_name=rule_name,
        )
        self.pending_tags = []
        return True

    def _handle_step(self, index: int, stripped: str) -> bool:
        m = _STEP_RE.match(stripped)
        if m is None:
            return False
        if self.scenario is None:
            raise _syntax("step outside a Scenario", line=index, path=self.path)
        text = (m.group("text") or "").strip()
        step = Step(m.group("kw"), text, index)
        self.scenario = replace(self.scenario, steps=self.scenario.steps + (step,))
        return True

    def _handle_description(self, stripped: str) -> None:
        if self.scenario is not None:
            self.scenario_description.append(stripped)
        elif self.current_rule_index is not None:
            self.rule_descriptions[self.current_rule_index].append(stripped)
        elif self.feature is not None:
            self.feature_description.append(stripped)

    def _flush_scenario(self) -> None:
        if self.scenario is None:
            return
        if self.scenario_description:
            description = "\n".join(self.scenario_description).strip()
            if description:
                self.scenario = replace(self.scenario, description=description)
        self.scenario_description.clear()
        if self.current_rule_index is not None:
            self.rule_scenarios[self.current_rule_index].append(self.scenario)
        else:
            self.top_scenarios.append(self.scenario)
        self.scenario = None

    def _finalize(self) -> Feature:
        if self.feature is None:
            raise _syntax("no Feature block found", line=0, path=self.path)
        self._flush_scenario()

        final_rules: list[Rule] = []
        for idx, rule in enumerate(self.rules_list):
            description = "\n".join(self.rule_descriptions.get(idx, [])).strip()
            final_rules.append(
                replace(
                    rule,
                    description=description,
                    scenarios=tuple(self.rule_scenarios.get(idx, [])),
                )
            )

        return replace(
            self.feature,
            description="\n".join(self.feature_description).strip(),
            scenarios=tuple(self.top_scenarios),
            rules=tuple(final_rules),
        )


def parse_feature(text: str, *, path: str = "") -> Feature:
    """Parse feature ``text`` into a :class:`Feature`.

    Raises :class:`GherkinParseError` (SML003/SML004) on the first fatal problem.
    """
    return _FeatureParser(path=path).parse(text)


def parse_feature_file(path: Path | str) -> Feature:
    """Read and parse a ``.feature`` file from disk.

    Markdown feature paths are rejected (SML004) because markdown-with-Gherkin
    is out of scope for the MVP.
    """
    p = Path(path)
    if p.suffix.lower() in _MARKDOWN_SUFFIXES:
        raise _unsupported(
            "markdown-with-Gherkin files are not supported in the MVP",
            line=0,
            path=str(p),
        )
    return parse_feature(read_text(p), path=str(p))


__all__ = [
    "GherkinParseError",
    "parse_feature",
    "parse_feature_file",
]
