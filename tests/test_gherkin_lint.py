"""Tests for Gherkin lint rules (required tags + duplicate identity)."""

from __future__ import annotations

from specmason.errors import (
    SML005_MISSING_REQ_TAG,
    SML006_MISSING_AC_TAG,
    SML007_DUPLICATE_SCENARIO_IDENTITY,
    SML008_UNKNOWN_REQUIREMENT_ID,
    SML009_UNKNOWN_CRITERION_ID,
)
from specmason.gherkin.lint import lint_feature, lint_feature_with_authority
from specmason.gherkin.parser import parse_feature

FEATURE = "Feature: F\n  @req-REQ-0001 @ac-AC-0001\n  Scenario: ok\n    Then c\n"


def _feature(text: str = FEATURE) -> object:
    return parse_feature(text, path="f.feature")


def test_lint_passes_when_tags_present() -> None:
    findings = lint_feature(_feature())  # type: ignore[arg-type]
    assert len(findings) == 0


def test_lint_missing_req_tag() -> None:
    text = "Feature: F\n  @ac-AC-0001\n  Scenario: s\n    Then c\n"
    findings = lint_feature(parse_feature(text, path="f.feature"))
    codes = [f.code for f in findings]
    assert SML005_MISSING_REQ_TAG in codes


def test_lint_missing_ac_tag() -> None:
    text = "Feature: F\n  @req-REQ-0001\n  Scenario: s\n    Then c\n"
    findings = lint_feature(parse_feature(text, path="f.feature"))
    codes = [f.code for f in findings]
    assert SML006_MISSING_AC_TAG in codes


def test_lint_malformed_req_tag_counts_as_missing() -> None:
    text = "Feature: F\n  @req-req-1 @ac-AC-0001\n  Scenario: s\n    Then c\n"
    findings = lint_feature(parse_feature(text, path="f.feature"))
    codes = [f.code for f in findings]
    assert SML005_MISSING_REQ_TAG in codes


def test_lint_detects_duplicate_identity() -> None:
    text = (
        "Feature: F\n"
        "  @req-REQ-0001 @ac-AC-0001\n"
        "  Scenario: one\n"
        "    Then c\n"
        "  @req-REQ-0001 @ac-AC-0001\n"
        "  Scenario: two\n"
        "    Then c\n"
    )
    findings = lint_feature(parse_feature(text, path="f.feature"))
    codes = [f.code for f in findings]
    assert SML007_DUPLICATE_SCENARIO_IDENTITY in codes


def test_lint_with_authority_flags_unknown_ids() -> None:
    text = "Feature: F\n  @req-REQ-0099 @ac-AC-0099\n  Scenario: s\n    Then c\n"
    feature = parse_feature(text, path="f.feature")
    findings = lint_feature_with_authority(
        feature,
        known_requirement_ids={"REQ-0001"},
        known_criterion_ids={"AC-0001"},
    )
    codes = [f.code for f in findings]
    assert SML008_UNKNOWN_REQUIREMENT_ID in codes
    assert SML009_UNKNOWN_CRITERION_ID in codes


def test_lint_standalone_skips_authority() -> None:
    text = "Feature: F\n  @req-REQ-0099 @ac-AC-0099\n  Scenario: s\n    Then c\n"
    feature = parse_feature(text, path="f.feature")
    findings = lint_feature_with_authority(
        feature, known_requirement_ids=None, known_criterion_ids=None
    )
    assert not findings.has_errors


def test_require_tags_can_be_disabled() -> None:
    text = "Feature: F\n  Scenario: s\n    Then c\n"
    feature = parse_feature(text, path="f.feature")
    findings = lint_feature(feature, require_req_tag=False, require_ac_tag=False)
    assert len(findings) == 0
