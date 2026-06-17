"""Verify SpecMason actively depends on and uses ledgercore primitives.

This mirrors the pattern in the Ledgerwerk family (e.g. taskledger's
``test_ledgercore_dependency.py``): the dependency is not just declared in
``pyproject.toml`` but exercised through SpecMason's own facade so the coupling
cannot silently regress.
"""

from __future__ import annotations

import sys

import ledgercore
from ledgercore.atomic import atomic_write_text
from ledgercore.ids import slugify_ref

import specmason.ids as sm_ids
from specmason.ids import (
    extract_identity,
    is_resource_reference,
    is_valid_criterion_id,
    is_valid_requirement_id,
    next_criterion_id,
    next_requirement_id,
)


def test_ledgercore_is_importable_and_versioned() -> None:
    assert isinstance(ledgercore.__version__, str)
    assert ledgercore.__version__


def test_specmason_ids_route_through_ledgercore() -> None:
    # Allocation via ledgercore next_prefixed_id.
    assert next_requirement_id(["REQ-0001", "REQ-0002"]) == "REQ-0003"
    assert next_criterion_id([]) == "AC-0001"

    # Validation uses ledgercore LedgerIdFormat plus canonical-width regex.
    assert is_valid_requirement_id("REQ-0001")
    assert not is_valid_requirement_id("REQ-1")
    assert is_valid_criterion_id("AC-0042")
    assert not is_valid_criterion_id("ZZ-0001")

    # slugify delegates to ledgercore.slugify_ref.
    assert sm_ids.slugify("Reject invalid login passwords!") == slugify_ref(
        "Reject invalid login passwords!"
    )

    # Refs via ledgercore.is_resource_ref.
    assert is_resource_reference("REQ-0001")


def test_tag_parsing_extracts_identity() -> None:
    assert sm_ids.parse_req_tag("@req-REQ-0001") == "REQ-0001"
    assert sm_ids.parse_ac_tag("@ac-AC-0001") == "AC-0001"
    req, ac = extract_identity(["@smoke", "@req-REQ-0007", "@ac-AC-0003"])
    assert (req, ac) == ("REQ-0007", "AC-0003")
    assert extract_identity(["@needs-review"]) == (None, None)


def test_ledgercore_in_sys_modules_after_import() -> None:
    # Importing specmason primitives pulls in ledgercore modules.
    for mod in (
        "ledgercore",
        "ledgercore.ids",
        "ledgercore.refs",
    ):
        assert mod in sys.modules, f"{mod} not imported by specmason"


def test_atomic_write_text_is_ledgercore_primitive(tmp_path) -> None:
    target = tmp_path / "out" / "report.json"
    atomic_write_text(target, "{}\n")
    assert target.read_text() == "{}\n"
