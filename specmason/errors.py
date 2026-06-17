"""Error hierarchy, finding codes, and structured findings for SpecMason.

SpecMason reports problems as structured :class:`Finding` records that carry a
stable ``SML`` code (see the MVP brief's finding-code table). The error base
class derives from a plain :class:`Exception`; ledgercore storage/path/json
errors are caught at the edges and re-raised as :class:`SpecMasonError`
subclasses so callers see one consistent hierarchy.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

# ---------------------------------------------------------------------------
# Finding codes (verbatim from the MVP brief).
# ---------------------------------------------------------------------------

SML001_INVALID_CONFIG = "SML001"
SML002_MISSING_CONFIGURED_PATH = "SML002"
SML003_INVALID_FEATURE_SYNTAX = "SML003"
SML004_UNSUPPORTED_GHERKIN_CONSTRUCT = "SML004"
SML005_MISSING_REQ_TAG = "SML005"
SML006_MISSING_AC_TAG = "SML006"
SML007_DUPLICATE_SCENARIO_IDENTITY = "SML007"
SML008_UNKNOWN_REQUIREMENT_ID = "SML008"
SML009_UNKNOWN_CRITERION_ID = "SML009"
SML010_INVALID_MAPPING_COMMENT = "SML010"
SML011_STALE_MAPPING_TARGET = "SML011"
SML012_MISSING_PYTEST_MAPPING = "SML012"
SML013_UNMAPPED_PYTEST_TEST = "SML013"
SML014_INVALID_INTENTIONAL_UNMAPPED_POLICY = "SML014"
SML015_EXPIRED_WAIVER = "SML015"
SML016_MISSING_WAIVER_REASON = "SML016"
SML017_EVIDENCE_MISSING_MAPPED_TEST = "SML017"
SML018_EVIDENCE_FAILED_MAPPED_TEST = "SML018"
SML019_GENERATED_FEATURE_NEEDS_REVIEW = "SML019"
SML020_NO_REQLEDGER_MANIFEST_STANDALONE = "SML020"
SML021_UNKNOWN_REQUIREMENT_AUTHORITY = "SML021"
SML022_CANDIDATE_MATCH_NOT_BINDING = "SML022"
SML023_BROWNFIELD_BEHAVIOR_REQUIRES_CLASSIFICATION = "SML023"

Severity = Literal["error", "warning", "info"]

# Codes that are informational rather than blocking.
INFO_CODES: frozenset[str] = frozenset(
    {SML019_GENERATED_FEATURE_NEEDS_REVIEW, SML022_CANDIDATE_MATCH_NOT_BINDING}
)


@dataclass(frozen=True)
class Finding:
    """A single structured diagnostic finding.

    ``location`` is a free-form string, typically ``"<path>:<line>"`` or just
    ``"<path>"``/``"<nodeid>"`` depending on the source artifact.
    """

    code: str
    severity: Severity
    message: str
    location: str = ""

    def is_error(self) -> bool:
        """Return True when this finding is a blocking error."""
        return self.severity == "error"

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-friendly dictionary."""
        return asdict(self)

    def render(self) -> str:
        """Render a compact human-readable line."""
        prefix = f"{self.location}: " if self.location else ""
        return f"{prefix}{self.code} {self.severity}: {self.message}"


@dataclass(frozen=True)
class Findings:
    """An ordered collection of findings with summary helpers."""

    items: tuple[Finding, ...] = field(default_factory=tuple)

    @classmethod
    def of(cls, *findings: Finding) -> Findings:
        """Build a collection from individual findings."""
        return cls(items=tuple(findings))

    def append(self, finding: Finding) -> Findings:
        """Return a new collection with the finding appended."""
        return Findings(items=self.items + (finding,))

    def extend(self, other: Findings) -> Findings:
        """Return a new collection concatenating another collection."""
        return Findings(items=self.items + other.items)

    def __iter__(self):  # type: ignore[no-untyped-def]
        return iter(self.items)

    def __len__(self) -> int:
        return len(self.items)

    @property
    def errors(self) -> tuple[Finding, ...]:
        """Only the blocking findings."""
        return tuple(f for f in self.items if f.is_error())

    @property
    def has_errors(self) -> bool:
        """True if at least one blocking finding is present."""
        return any(f.is_error() for f in self.items)

    def to_list(self) -> list[dict[str, Any]]:
        """Serialize all findings to a list of dictionaries."""
        return [f.to_dict() for f in self.items]

    def render_lines(self) -> list[str]:
        """Render all findings as human-readable lines."""
        return [f.render() for f in self.items]


# ---------------------------------------------------------------------------
# Exception hierarchy.
# ---------------------------------------------------------------------------


class SpecMasonError(Exception):
    """Base class for all SpecMason errors."""


class ConfigError(SpecMasonError):
    """Configuration loading or resolution failed (usage/config error)."""


class CheckError(SpecMasonError):
    """A ``check`` run found blocking findings (exit code 1)."""


class CoverageError(SpecMasonError):
    """A ``coverage`` run found blocking findings (exit code 1)."""


__all__ = [
    "CheckError",
    "ConfigError",
    "CoverageError",
    "Finding",
    "Findings",
    "INFO_CODES",
    "SML001_INVALID_CONFIG",
    "SML002_MISSING_CONFIGURED_PATH",
    "SML003_INVALID_FEATURE_SYNTAX",
    "SML004_UNSUPPORTED_GHERKIN_CONSTRUCT",
    "SML005_MISSING_REQ_TAG",
    "SML006_MISSING_AC_TAG",
    "SML007_DUPLICATE_SCENARIO_IDENTITY",
    "SML008_UNKNOWN_REQUIREMENT_ID",
    "SML009_UNKNOWN_CRITERION_ID",
    "SML010_INVALID_MAPPING_COMMENT",
    "SML011_STALE_MAPPING_TARGET",
    "SML012_MISSING_PYTEST_MAPPING",
    "SML013_UNMAPPED_PYTEST_TEST",
    "SML014_INVALID_INTENTIONAL_UNMAPPED_POLICY",
    "SML015_EXPIRED_WAIVER",
    "SML016_MISSING_WAIVER_REASON",
    "SML017_EVIDENCE_MISSING_MAPPED_TEST",
    "SML018_EVIDENCE_FAILED_MAPPED_TEST",
    "SML019_GENERATED_FEATURE_NEEDS_REVIEW",
    "SML020_NO_REQLEDGER_MANIFEST_STANDALONE",
    "SML021_UNKNOWN_REQUIREMENT_AUTHORITY",
    "SML022_CANDIDATE_MATCH_NOT_BINDING",
    "SML023_BROWNFIELD_BEHAVIOR_REQUIRES_CLASSIFICATION",
    "Severity",
    "SpecMasonError",
]
