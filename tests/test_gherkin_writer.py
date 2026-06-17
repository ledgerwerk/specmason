"""Tests for Gherkin writer: deterministic rendering and draft generation."""

from __future__ import annotations

from specmason.errors import SML019_GENERATED_FEATURE_NEEDS_REVIEW
from specmason.gherkin.parser import parse_feature
from specmason.gherkin.writer import (
    build_feature_for_criterion,
    feature_filename_for,
    needs_review_finding,
    render_feature,
)


def test_render_is_deterministic_round_trip() -> None:
    text = (
        "Feature: Login\n"
        "  @req-REQ-0001 @ac-AC-0001\n"
        "  Scenario: Reject invalid password\n"
        "    Given a registered user exists\n"
        "    Then login is rejected\n"
    )
    feature = parse_feature(text, path="login.feature")
    rendered_a = render_feature(feature)
    rendered_b = render_feature(parse_feature(rendered_a))
    assert rendered_a == rendered_b
    assert rendered_a.endswith("\n")


def test_generated_feature_has_required_tags_and_needs_review() -> None:
    feature = build_feature_for_criterion(
        req_id="REQ-0001",
        ac_id="AC-0001",
        title="Reject invalid login passwords",
        statement="Login is rejected when an invalid password is submitted.",
    )
    assert needs_review_finding(feature) == SML019_GENERATED_FEATURE_NEEDS_REVIEW
    scenario = feature.scenarios[0]
    assert "@req-REQ-0001" in scenario.tags
    assert "@ac-AC-0001" in scenario.tags
    assert "@needs-review" in scenario.tags
    assert [s.keyword for s in scenario.steps] == ["Given", "When", "Then"]
    text = render_feature(feature)
    assert "Feature: Reject invalid login passwords" in text
    assert "@needs-review" in text


def test_generated_feature_is_deterministic() -> None:
    a = build_feature_for_criterion(
        req_id="REQ-0001", ac_id="AC-0001", title="T", statement="S"
    )
    b = build_feature_for_criterion(
        req_id="REQ-0001", ac_id="AC-0001", title="T", statement="S"
    )
    assert render_feature(a) == render_feature(b)


def test_feature_filename_is_deterministic() -> None:
    name = feature_filename_for("REQ-0001", "AC-0001", title="Reject passwords!")
    assert name == "req-0001-ac-0001.feature"
    assert feature_filename_for("REQ-0002", "AC-0005") == "req-0002-ac-0005.feature"
