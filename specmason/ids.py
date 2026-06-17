"""ID and ref helpers for SpecMason, backed by :mod:`ledgercore`.

This module is a thin facade over ledgercore's prefixed-ID and resource-ref
primitives. SpecMason uses ``REQ-NNNN`` requirement IDs and ``AC-NNNN``
criterion IDs (both owned by ReqLedger; SpecMason only reads and references
them), plus ``@req-REQ-NNNN`` / ``@ac-AC-NNNN`` Gherkin tags.

Using ledgercore here keeps allocation, parsing, and slug formatting consistent
with the rest of the Ledgerwerk family and avoids reinventing ID validation.
"""

from __future__ import annotations

import re

from ledgercore.ids import LedgerIdFormat, next_prefixed_id, slugify_ref
from ledgercore.refs import is_resource_ref, parse_local_ref

# Requirement and criterion ID formats (4-digit zero-padded). These mirror the
# ReqLedger record formats; SpecMason is a read-only consumer but still needs to
# validate and compare IDs deterministically.
REQUIREMENT_ID_FORMAT = LedgerIdFormat(prefix="REQ", separator="-", width=4)
CRITERION_ID_FORMAT = LedgerIdFormat(prefix="AC", separator="-", width=4)

# Gherkin tag patterns: ``@req-REQ-0001`` and ``@ac-AC-0001``. The 4-digit form
# is required so that generated/accepted IDs stay canonical.
_REQ_TAG_RE = re.compile(r"^@req-(REQ-(?P<num>\d{4,}))$", re.IGNORECASE)
_AC_TAG_RE = re.compile(r"^@ac-(AC-(?P<num>\d{4,}))$", re.IGNORECASE)

# Plain id patterns (no ``@`` prefix) used to validate mapping-comment values.
_REQ_ID_RE = re.compile(r"^REQ-\d{4,}$")
_AC_ID_RE = re.compile(r"^AC-\d{4,}$")


def next_requirement_id(existing_ids: list[str]) -> str:
    """Return the next ``REQ-NNNN`` id not present in ``existing_ids``."""
    return next_prefixed_id("REQ", existing_ids)


def next_criterion_id(existing_ids: list[str]) -> str:
    """Return the next ``AC-NNNN`` id not present in ``existing_ids``."""
    return next_prefixed_id("AC", existing_ids)


def is_valid_requirement_id(value: str) -> bool:
    """Return True if ``value`` is a canonical ``REQ-NNNN`` requirement id."""
    return bool(_REQ_ID_RE.fullmatch(value)) and REQUIREMENT_ID_FORMAT.is_valid(value)


def is_valid_criterion_id(value: str) -> bool:
    """Return True if ``value`` is a canonical ``AC-NNNN`` criterion id."""
    return bool(_AC_ID_RE.fullmatch(value)) and CRITERION_ID_FORMAT.is_valid(value)


def is_resource_reference(value: str) -> bool:
    """Return True if ``value`` parses as a ledgercore local resource ref.

    Used for validating cross-references such as evidence/evidence refs.
    """
    return is_resource_ref(value)


def parse_local_resource(value: str) -> tuple[str, int]:
    """Parse a local ref like ``REQ-0001`` into ``(kind, number)``.

    The returned ``kind`` is lowercased by ledgercore (e.g. ``"req"``).
    """
    ref = parse_local_ref(value)
    return ref.kind, ref.number


def slugify(text: str) -> str:
    """Slugify arbitrary text using ledgercore's slug normalizer."""
    return slugify_ref(text)


def parse_req_tag(tag: str) -> str | None:
    """Return the requirement id in a ``@req-REQ-0001`` tag, or ``None``."""
    match = _REQ_TAG_RE.fullmatch(tag.strip())
    if match is None:
        return None
    return match.group(1).upper()


def parse_ac_tag(tag: str) -> str | None:
    """Return the criterion id in a ``@ac-AC-0001`` tag, or ``None``."""
    match = _AC_TAG_RE.fullmatch(tag.strip())
    if match is None:
        return None
    return match.group(1).upper()


def extract_identity(tags: list[str]) -> tuple[str | None, str | None]:
    """Extract ``(req_id, ac_id)`` from a scenario's tag list.

    Returns ``(None, None)`` when no identity tags are present.
    """
    req_id: str | None = None
    ac_id: str | None = None
    for tag in tags:
        if req_id is None:
            req_id = parse_req_tag(tag)
        if ac_id is None:
            ac_id = parse_ac_tag(tag)
        if req_id is not None and ac_id is not None:
            break
    return req_id, ac_id


__all__ = [
    "CRITERION_ID_FORMAT",
    "REQUIREMENT_ID_FORMAT",
    "extract_identity",
    "is_resource_reference",
    "is_valid_criterion_id",
    "is_valid_requirement_id",
    "next_criterion_id",
    "next_requirement_id",
    "parse_ac_tag",
    "parse_local_resource",
    "parse_req_tag",
    "slugify",
]
