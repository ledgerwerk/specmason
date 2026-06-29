"""Pytest mapping comments and intentional-unmapped policy.

Mapping comments bind a pytest test to a requirement/criterion:

- full: ``# specmason: req=REQ-0001 ac=AC-0001 feature=specs/.../x.feature``
- short: ``# sm: req=REQ-0001 ac=AC-0001``
- inline waiver: ``# specmason: unmapped=<reason>``

Central waivers live in ``intentional-unmapped.json``. Waived tests appear as
``waived``, never ``mapped``; missing reasons (SML016) and expired waivers
(SML015) are errors; an invalid policy file is SML014. Invalid mapping comments
are SML010.

Policy loading uses :func:`ledgercore.jsonio.load_json_object`.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from ledgercore.errors import JsonStoreError
from ledgercore.jsonio import load_json_object

from specmason.errors import (
    SML010_INVALID_MAPPING_COMMENT,
    SML014_INVALID_INTENTIONAL_UNMAPPED_POLICY,
    SML015_EXPIRED_WAIVER,
    SML016_MISSING_WAIVER_REASON,
    Finding,
    Findings,
)
from specmason.pytest_discovery import DiscoveredTest

_KV_RE = re.compile(r"(\w+)=(\S+)")
_COMMENT_RE = re.compile(r"^#\s*(?P<prefix>specmason|sm)\s*:\s*(?P<body>.*)$")
_UNMAPPED_RE = re.compile(r"unmapped\s*=\s*(?P<reason>.+)$")


@dataclass(frozen=True)
class Mapping:
    """A requirement/criterion mapping parsed from a comment."""

    req_id: str
    ac_id: str
    feature: str = ""
    line: int = 0
    raw: str = ""

    @property
    def is_valid(self) -> bool:
        return bool(self.req_id and self.ac_id)


@dataclass(frozen=True)
class InlineWaiver:
    """An inline ``unmapped=<reason>`` waiver parsed from a comment."""

    reason: str
    line: int = 0


@dataclass(frozen=True)
class PolicyWaiver:
    """A central intentional-unmapped waiver for a node id."""

    nodeid: str
    reason: str
    owner: str = ""
    expires: str = ""


@dataclass(frozen=True)
class TestMapping:
    """A discovered test with its parsed mappings/waiver and resolved status."""

    __test__ = False

    nodeid: str
    file: str
    name: str
    class_name: str
    lineno: int
    mappings: tuple[Mapping, ...] = ()
    inline_waiver: InlineWaiver | None = None
    central_waiver: PolicyWaiver | None = None

    @property
    def is_mapped(self) -> bool:
        return any(m.is_valid for m in self.mappings)

    @property
    def is_waived(self) -> bool:
        return self.inline_waiver is not None or self.central_waiver is not None

    @property
    def status(self) -> str:
        if self.is_waived:
            return "waived"
        if self.is_mapped:
            return "mapped"
        return "unmapped"

    def criterion_ids(self) -> tuple[str, ...]:
        """Return ``(req_id, ac_id)`` pairs for each valid mapping."""
        return tuple((m.req_id, m.ac_id) for m in self.mappings if m.is_valid)


@dataclass(frozen=True)
class MappingInventory:
    """All discovered tests with parsed mappings plus findings."""

    tests: tuple[TestMapping, ...] = ()
    central_waivers: dict[str, PolicyWaiver] = field(default_factory=dict)
    findings: Findings = field(default_factory=Findings)

    def to_dict(self) -> dict[str, object]:
        return {
            "tests": [_test_dict(t) for t in self.tests],
            "central_waivers": {
                k: _waiver_dict(v) for k, v in self.central_waivers.items()
            },
            "findings": self.findings.to_list(),
        }


def _waiver_dict(w: PolicyWaiver) -> dict[str, str]:
    return {
        "nodeid": w.nodeid,
        "reason": w.reason,
        "owner": w.owner,
        "expires": w.expires,
    }


def _test_dict(t: TestMapping) -> dict[str, object]:
    return {
        "nodeid": t.nodeid,
        "file": t.file,
        "name": t.name,
        "class_name": t.class_name,
        "lineno": t.lineno,
        "status": t.status,
        "mappings": [
            {"req_id": m.req_id, "ac_id": m.ac_id, "feature": m.feature}
            for m in t.mappings
        ],
        "inline_waiver": (
            {"reason": t.inline_waiver.reason} if t.inline_waiver is not None else None
        ),
        "central_waiver": _waiver_dict(t.central_waiver) if t.central_waiver else None,
    }


def parse_comment(line: str) -> Mapping | InlineWaiver | None:
    """Parse a single comment line into a :class:`Mapping` or :class:`InlineWaiver`.

    Returns ``None`` for non-SpecMason comments.
    """
    match = _COMMENT_RE.match(line.strip())
    if match is None:
        return None
    body = match.group("body").strip()
    unmapped_match = _UNMAPPED_RE.match(body)
    if unmapped_match is not None:
        return InlineWaiver(reason=unmapped_match.group("reason").strip())
    pairs = dict(_KV_RE.findall(body))
    req_id = pairs.get("req", "")
    ac_id = pairs.get("ac", "")
    feature = pairs.get("feature", "")
    if not req_id and not ac_id:
        return None
    return Mapping(req_id=req_id, ac_id=ac_id, feature=feature, raw=line.strip())


def parse_preceding_comments(
    comments: Iterable[str],
) -> tuple[tuple[Mapping, ...], InlineWaiver | None]:
    """Parse the comment block preceding a test into mappings and a waiver."""
    mappings: list[Mapping] = []
    waiver: InlineWaiver | None = None
    for index, line in enumerate(comments):
        parsed = parse_comment(line)
        if isinstance(parsed, Mapping):
            mappings.append(parsed)
        elif isinstance(parsed, InlineWaiver):
            waiver = InlineWaiver(reason=parsed.reason, line=index)
    return tuple(mappings), waiver


def _validate_expires(expires: str, *, nodeid: str, findings: Findings) -> Findings:
    if not expires:
        return findings
    try:
        expiry = date.fromisoformat(expires)
    except ValueError:
        return findings.append(
            Finding(
                SML014_INVALID_INTENTIONAL_UNMAPPED_POLICY,
                "error",
                f"invalid 'expires' date for {nodeid}: {expires!r}",
            )
        )
    if expiry < date.today():
        return findings.append(
            Finding(
                SML015_EXPIRED_WAIVER,
                "error",
                f"waiver for {nodeid} expired on {expires}",
            )
        )
    return findings


def load_intentional_unmapped_policy(
    path: Path | str,
) -> tuple[dict[str, PolicyWaiver], Findings]:
    """Load and validate the central intentional-unmapped policy file.

    Returns ``(nodeid -> PolicyWaiver, findings)``. A missing file is treated as
    an empty policy (not an error) so standalone projects without one still work.
    """
    p = Path(path)
    if not p.is_file():
        return {}, Findings()
    try:
        data = load_json_object(p, label="intentional-unmapped policy", missing="error")
    except JsonStoreError as exc:
        return {}, Findings().append(
            Finding(
                SML014_INVALID_INTENTIONAL_UNMAPPED_POLICY,
                "error",
                str(exc),
                str(p),
            )
        )

    raw_items = data.get("items", [])
    if not isinstance(raw_items, list):
        return {}, Findings().append(
            Finding(
                SML014_INVALID_INTENTIONAL_UNMAPPED_POLICY,
                "error",
                "'items' must be an array",
                str(p),
            )
        )

    findings = Findings()
    waivers: dict[str, PolicyWaiver] = {}
    for item in raw_items:
        if not isinstance(item, dict):
            findings = findings.append(
                Finding(
                    SML014_INVALID_INTENTIONAL_UNMAPPED_POLICY,
                    "error",
                    "each waiver item must be an object",
                    str(p),
                )
            )
            continue
        nodeid = str(item.get("nodeid", "")).strip()
        reason = str(item.get("reason", "")).strip()
        owner = str(item.get("owner", "")).strip()
        expires = str(item.get("expires", "")).strip()
        if not nodeid:
            findings = findings.append(
                Finding(
                    SML014_INVALID_INTENTIONAL_UNMAPPED_POLICY,
                    "error",
                    "waiver item is missing 'nodeid'",
                    str(p),
                )
            )
            continue
        if not reason:
            findings = findings.append(
                Finding(
                    SML016_MISSING_WAIVER_REASON,
                    "error",
                    f"waiver for {nodeid} is missing a reason",
                    str(p),
                )
            )
            continue
        findings = _validate_expires(expires, nodeid=nodeid, findings=findings)
        waivers[nodeid] = PolicyWaiver(
            nodeid=nodeid, reason=reason, owner=owner, expires=expires
        )

    return waivers, findings


def build_inventory(
    discovered: Iterable[DiscoveredTest],
    *,
    central_waivers: dict[str, PolicyWaiver] | None = None,
    findings: Findings | None = None,
) -> MappingInventory:
    """Build a :class:`MappingInventory` from discovered tests."""
    waivers = central_waivers or {}
    combined = findings or Findings()
    tests: list[TestMapping] = []

    for test in discovered:
        mappings, inline_waiver = parse_preceding_comments(test.preceding_comments)
        invalid = [m for m in mappings if not m.is_valid]
        for bad in invalid:
            combined = combined.append(
                Finding(
                    SML010_INVALID_MAPPING_COMMENT,
                    "error",
                    f"invalid mapping comment near {test.nodeid}: {bad.raw!r}",
                    f"{test.file}:{test.lineno}",
                )
            )
        valid_mappings = tuple(m for m in mappings if m.is_valid)
        central = waivers.get(test.nodeid)
        tests.append(
            TestMapping(
                nodeid=test.nodeid,
                file=test.file,
                name=test.name,
                class_name=test.class_name,
                lineno=test.lineno,
                mappings=valid_mappings,
                inline_waiver=inline_waiver,
                central_waiver=central,
            )
        )

    return MappingInventory(
        tests=tuple(tests), central_waivers=dict(waivers), findings=combined
    )


__all__ = [
    "InlineWaiver",
    "Mapping",
    "MappingInventory",
    "PolicyWaiver",
    "TestMapping",
    "build_inventory",
    "load_intentional_unmapped_policy",
    "parse_comment",
    "parse_preceding_comments",
]
