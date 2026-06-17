"""Tests for the Gherkin parser (supported subset + fail-closed unsupported)."""

from __future__ import annotations

import pytest

from specmason.errors import (
    SML003_INVALID_FEATURE_SYNTAX,
    SML004_UNSUPPORTED_GHERKIN_CONSTRUCT,
)
from specmason.gherkin.parser import (
    GherkinParseError,
    parse_feature,
    parse_feature_file,
)


def test_parse_feature_rule_scenario_steps_tags() -> None:
    text = (
        "@auth @domain\n"
        "Feature: Login\n"
        "  Users can log in.\n"
        "\n"
        "  Rule: invalid logins are rejected\n"
        "\n"
        "    @req-REQ-0001 @ac-AC-0001\n"
        "    Scenario: Reject invalid password\n"
        "      Given a registered user exists\n"
        "      When the user submits an invalid password\n"
        "      Then login is rejected\n"
    )
    feature = parse_feature(text, path="login.feature")
    assert feature.name == "Login"
    assert feature.tags == ("@auth", "@domain")
    assert feature.description == "Users can log in."
    assert len(feature.rules) == 1
    rule = feature.rules[0]
    assert rule.name == "invalid logins are rejected"
    assert len(rule.scenarios) == 1
    scenario = rule.scenarios[0]
    assert scenario.keyword == "Scenario"
    assert scenario.name == "Reject invalid password"
    assert scenario.tags == ("@req-REQ-0001", "@ac-AC-0001")
    assert scenario.rule_name == "invalid logins are rejected"
    assert [s.keyword for s in scenario.steps] == ["Given", "When", "Then"]
    assert scenario.steps[1].text == "the user submits an invalid password"
    assert len(feature.all_scenarios) == 1


def test_parse_example_is_synonym_for_scenario() -> None:
    text = (
        "Feature: X\n"
        "  Example: a case\n"
        "    Then ok\n"
    )
    feature = parse_feature(text)
    assert feature.scenarios[0].keyword == "Example"


def test_parse_top_level_scenario_without_rule() -> None:
    text = (
        "@req-REQ-0002 @ac-AC-0002\n"
        "Feature: X\n"
        "  Scenario: top\n"
        "    Given c\n"
    )
    feature = parse_feature(text)
    assert len(feature.scenarios) == 1
    assert feature.scenarios[0].name == "top"


def test_parse_preserves_line_numbers() -> None:
    text = "Feature: X\n\n  Scenario: s\n    Given c\n"
    feature = parse_feature(text)
    assert feature.line == 1
    assert feature.scenarios[0].line == 3
    assert feature.scenarios[0].steps[0].line == 4


def test_parse_rejects_scenario_outline() -> None:
    text = "Feature: X\n  Scenario Outline: o\n    Given <x>\n"
    with pytest.raises(GherkinParseError) as exc:
        parse_feature(text)
    assert exc.value.code == SML004_UNSUPPORTED_GHERKIN_CONSTRUCT
    assert exc.value.line == 2


def test_parse_rejects_scenario_template() -> None:
    text = "Feature: X\n  Scenario Template: o\n    Given c\n"
    with pytest.raises(GherkinParseError) as exc:
        parse_feature(text)
    assert exc.value.code == SML004_UNSUPPORTED_GHERKIN_CONSTRUCT


def test_parse_rejects_background() -> None:
    text = "Feature: X\n  Background:\n    Given c\n"
    with pytest.raises(GherkinParseError) as exc:
        parse_feature(text)
    assert exc.value.code == SML004_UNSUPPORTED_GHERKIN_CONSTRUCT


def test_parse_rejects_examples_table() -> None:
    text = "Feature: X\n  Scenario: s\n    Given c\n  Examples:\n    | x |\n"
    with pytest.raises(GherkinParseError) as exc:
        parse_feature(text)
    assert exc.value.code == SML004_UNSUPPORTED_GHERKIN_CONSTRUCT


def test_parse_rejects_data_table() -> None:
    text = "Feature: X\n  Scenario: s\n    Given c\n      | a | b |\n"
    with pytest.raises(GherkinParseError) as exc:
        parse_feature(text)
    assert exc.value.code == SML004_UNSUPPORTED_GHERKIN_CONSTRUCT


def test_parse_rejects_doc_string() -> None:
    text = 'Feature: X\n  Scenario: s\n    Given c\n      """\n      multi\n      """\n'
    with pytest.raises(GherkinParseError) as exc:
        parse_feature(text)
    assert exc.value.code == SML004_UNSUPPORTED_GHERKIN_CONSTRUCT


def test_parse_rejects_wildcard_step() -> None:
    text = "Feature: X\n  Scenario: s\n    * something\n"
    with pytest.raises(GherkinParseError) as exc:
        parse_feature(text)
    assert exc.value.code == SML004_UNSUPPORTED_GHERKIN_CONSTRUCT


def test_parse_rejects_multiple_feature_blocks() -> None:
    text = "Feature: A\n  Scenario: s\n    Given c\nFeature: B\n"
    with pytest.raises(GherkinParseError) as exc:
        parse_feature(text)
    assert exc.value.code == SML004_UNSUPPORTED_GHERKIN_CONSTRUCT


def test_parse_rejects_step_outside_scenario() -> None:
    text = "Feature: X\n  Given c\n"
    with pytest.raises(GherkinParseError) as exc:
        parse_feature(text)
    assert exc.value.code == SML003_INVALID_FEATURE_SYNTAX


def test_parse_rejects_no_feature() -> None:
    with pytest.raises(GherkinParseError) as exc:
        parse_feature("Rule: r\n")
    assert exc.value.code == SML003_INVALID_FEATURE_SYNTAX


def test_parse_feature_file_rejects_markdown(tmp_path) -> None:
    md = tmp_path / "spec.md"
    md.write_text("Feature: X\n", encoding="utf-8")
    with pytest.raises(GherkinParseError) as exc:
        parse_feature_file(md)
    assert exc.value.code == SML004_UNSUPPORTED_GHERKIN_CONSTRUCT


def test_parse_feature_file_reads_disk(tmp_path) -> None:
    f = tmp_path / "login.feature"
    f.write_text("Feature: Login\n  Scenario: s\n    Then ok\n", encoding="utf-8")
    feature = parse_feature_file(f)
    assert feature.name == "Login"
    assert feature.path == str(f)
