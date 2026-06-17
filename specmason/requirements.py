"""ReqLedger manifest/export reader.

SpecMason is a **read-only** consumer of ReqLedger's deterministic JSON. It never
imports ReqLedger at runtime. The manifest/export shape (derived from the real
reqledger package) is::

    {
      "schema_version": 1,
      "tool": "reqledger",
      "requirements": [
        {
          "id": "REQ-0001", "title": "...", "path": "...",
          "kind": "functional", "status": "accepted", "priority": "must",
          "tags": [], "source": "manual", "source_refs": [],
          "criteria": [
            {"id": "AC-0001", "statement": "...",
             "verification": "behavior", "status": "accepted", "tags": []}
          ],
          "refs": {"tasks": [], "architecture": [], "specs": [], "evidence": []}
        }
      ]
    }

Loading uses :func:`ledgercore.jsonio.load_json_object` so malformed JSON is
reported as a :class:`RequirementsError` rather than crashing.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from ledgercore.errors import JsonStoreError
from ledgercore.jsonio import load_json_object

from specmason.errors import SpecMasonError

BEHAVIOR_VERIFICATION = "behavior"
ACCEPTED_STATUS = "accepted"


class RequirementsError(SpecMasonError):
    """Raised when a ReqLedger manifest cannot be read or is malformed."""


@dataclass(frozen=True)
class Criterion:
    """An acceptance criterion read from a ReqLedger export."""

    id: str
    statement: str
    verification: str
    status: str
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class Requirement:
    """A requirement read from a ReqLedger export."""

    id: str
    title: str
    kind: str
    status: str
    priority: str
    path: str = ""
    tags: tuple[str, ...] = ()
    source: str = ""
    source_refs: tuple[str, ...] = ()
    criteria: tuple[Criterion, ...] = ()
    spec_refs: tuple[str, ...] = ()
    task_refs: tuple[str, ...] = ()
    arch_refs: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class RequirementsIndex:
    """Lookup indexes over a loaded manifest."""

    requirements: tuple[Requirement, ...] = ()
    by_id: dict[str, Requirement] = field(default_factory=dict)
    criterion_by_id: dict[str, tuple[str, Criterion]] = field(default_factory=dict)
    # Accepted behavior criteria only (used for behavior coverage).
    accepted_behavior_ac_ids: frozenset[str] = field(default_factory=frozenset)

    @property
    def requirement_ids(self) -> frozenset[str]:
        return frozenset(self.by_id)

    @property
    def criterion_ids(self) -> frozenset[str]:
        return frozenset(self.criterion_by_id)

    def criterion(self, ac_id: str) -> tuple[str, Criterion] | None:
        """Return ``(req_id, criterion)`` for an AC id, or ``None``."""
        return self.criterion_by_id.get(ac_id)

    def is_accepted_behavior(self, ac_id: str) -> bool:
        """True when the criterion is accepted with ``verification='behavior'``."""
        return ac_id in self.accepted_behavior_ac_ids


def _as_str_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(v) for v in value]
    return []


def _criterion_from_dict(data: dict[str, object]) -> Criterion:
    return Criterion(
        id=str(data.get("id", "")),
        statement=str(data.get("statement", "")),
        verification=str(data.get("verification", "")),
        status=str(data.get("status", "")),
        tags=tuple(_as_str_list(data.get("tags"))),
    )


def _requirement_from_dict(data: dict[str, object]) -> Requirement:
    raw_criteria = data.get("criteria")
    if raw_criteria is None:
        criteria: tuple[Criterion, ...] = ()
    elif isinstance(raw_criteria, list):
        criteria = tuple(
            _criterion_from_dict(c) for c in raw_criteria if isinstance(c, dict)
        )
    else:
        criteria = ()
    refs = data.get("refs")
    spec_refs = _as_str_list(data.get("spec_refs"))
    task_refs = _as_str_list(data.get("task_refs"))
    arch_refs = _as_str_list(data.get("arch_refs"))
    evidence_refs = _as_str_list(data.get("evidence_refs"))
    if isinstance(refs, dict):
        spec_refs = _as_str_list(refs.get("specs", spec_refs))
        task_refs = _as_str_list(refs.get("tasks", task_refs))
        arch_refs = _as_str_list(refs.get("architecture", arch_refs))
        evidence_refs = _as_str_list(refs.get("evidence", evidence_refs))
    return Requirement(
        id=str(data.get("id", "")),
        title=str(data.get("title", "")),
        kind=str(data.get("kind", "")),
        status=str(data.get("status", "")),
        priority=str(data.get("priority", "")),
        path=str(data.get("path", "")),
        tags=tuple(_as_str_list(data.get("tags"))),
        source=str(data.get("source", "")),
        source_refs=tuple(_as_str_list(data.get("source_refs"))),
        criteria=criteria,
        spec_refs=tuple(spec_refs),
        task_refs=tuple(task_refs),
        arch_refs=tuple(arch_refs),
        evidence_refs=tuple(evidence_refs),
    )


def build_index(records: Iterable[Requirement]) -> RequirementsIndex:
    """Build lookup indexes from requirement records."""
    by_id: dict[str, Requirement] = {}
    criterion_by_id: dict[str, tuple[str, Criterion]] = {}
    accepted_behavior: set[str] = set()
    for req in records:
        by_id[req.id] = req
        for crit in req.criteria:
            criterion_by_id[crit.id] = (req.id, crit)
            is_behavior = (
                crit.status == ACCEPTED_STATUS
                and crit.verification == BEHAVIOR_VERIFICATION
            )
            if is_behavior:
                accepted_behavior.add(crit.id)
    return RequirementsIndex(
        requirements=tuple(records),
        by_id=by_id,
        criterion_by_id=criterion_by_id,
        accepted_behavior_ac_ids=frozenset(accepted_behavior),
    )


def load_manifest(path: Path | str) -> RequirementsIndex:
    """Load and index a ReqLedger manifest/export JSON file.

    Raises :class:`RequirementsError` on missing/invalid files.
    """
    p = Path(path)
    try:
        data = load_json_object(p, label="requirements manifest", missing="error")
    except JsonStoreError as exc:
        raise RequirementsError(str(exc)) from exc
    raw_requirements = data.get("requirements")
    if raw_requirements is None:
        raise RequirementsError(f"manifest has no 'requirements' array: {p}")
    if not isinstance(raw_requirements, list):
        raise RequirementsError("'requirements' must be an array")
    records = [
        _requirement_from_dict(r) for r in raw_requirements if isinstance(r, dict)
    ]
    records.sort(key=lambda r: r.id)
    return build_index(records)


__all__ = [
    "ACCEPTED_STATUS",
    "BEHAVIOR_VERIFICATION",
    "Criterion",
    "Requirement",
    "RequirementsError",
    "RequirementsIndex",
    "build_index",
    "load_manifest",
]
