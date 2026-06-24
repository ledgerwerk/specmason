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
    text = "Feature: X\n  Example: a case\n    Then ok\n"
    feature = parse_feature(text)
    assert feature.scenarios[0].keyword == "Example"


def test_parse_top_level_scenario_without_rule() -> None:
    text = "@req-REQ-0002 @ac-AC-0002\nFeature: X\n  Scenario: top\n    Given c\n"
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
    assert feature.path == str(f)


# ---------------------------------------------------------------------------
# Official parser tests (gherkin-official adapter)
# ---------------------------------------------------------------------------


def test_parse_official_background() -> None:
    from specmason.gherkin.official import parse_feature_official

    text = (
        "Feature: X\n"
        "  Background:\n"
        "    Given a common precondition\n"
        "  Scenario: s\n"
        "    Then ok\n"
    )
    feat = parse_feature_official(text, path="bg.feature")
    assert feat.background is not None
    assert feat.background.name == ""
    assert len(feat.background.steps) == 1
    assert feat.background.steps[0].keyword == "Given"
    assert feat.background.steps[0].text == "a common precondition"


def test_parse_official_scenario_outline_with_examples() -> None:
    from specmason.gherkin.official import parse_feature_official

    text = (
        "Feature: X\n"
        "  Scenario Outline: eating <n>\n"
        "    Given there are <n> cucumbers\n"
        "    Then I have <left> left\n"
        "    Examples:\n"
        "      | n | left |\n"
        "      | 5 | 3    |\n"
        "      | 7 | 5    |\n"
    )
    feat = parse_feature_official(text, path="ol.feature")
    assert len(feat.outline_scenarios) == 1
    outline = feat.outline_scenarios[0]
    assert outline.keyword == "Scenario Outline"
    assert outline.name == "eating <n>"
    assert len(outline.examples) == 1
    ex = outline.examples[0]
    assert [c.value for c in ex.header.cells] == ["n", "left"]
    assert len(ex.body) == 2
    assert [c.value for c in ex.body[0].cells] == ["5", "3"]


def test_parse_official_data_table() -> None:
    from specmason.gherkin.official import parse_feature_official

    text = (
        "Feature: X\n"
        "  Scenario: s\n"
        "    Given a table:\n"
        "      | a | b |\n"
        "      | 1 | 2 |\n"
        "    Then ok\n"
    )
    feat = parse_feature_official(text, path="dt.feature")
    step = feat.scenarios[0].steps[0]
    assert step.argument is not None
    assert step.argument.kind == "datatable"
    assert len(step.argument.rows) == 2
    assert [c.value for c in step.argument.rows[0].cells] == ["a", "b"]
    assert [c.value for c in step.argument.rows[1].cells] == ["1", "2"]


def test_parse_official_doc_string() -> None:
    from specmason.gherkin.official import parse_feature_official

    text = (
        "Feature: X\n"
        "  Scenario: s\n"
        "    Given content:\n"
        '      """\n'
        "      hello world\n"
        '      """\n'
        "    Then ok\n"
    )
    feat = parse_feature_official(text, path="ds.feature")
    step = feat.scenarios[0].steps[0]
    assert step.argument is not None
    assert step.argument.kind == "docstring"
    assert step.argument.content.strip() == "hello world"


def test_parse_official_wildcard_step() -> None:
    from specmason.gherkin.official import parse_feature_official

    text = "Feature: X\n  Scenario: s\n    * doing something\n    Then ok\n"
    feat = parse_feature_official(text, path="wc.feature")
    assert feat.scenarios[0].steps[0].keyword == "*"
    assert feat.scenarios[0].steps[0].text == "doing something"


def test_parse_official_language_header() -> None:
    from specmason.gherkin.official import parse_feature_official

    text = "# language: en\nFeature: X\n  Scenario: s\n    Then ok\n"
    feat = parse_feature_official(text, path="en.feature")
    assert feat.language == "en"
    assert feat.scenarios[0].keyword == "Scenario"


def test_parse_official_rule_with_background() -> None:
    from specmason.gherkin.official import parse_feature_official

    text = (
        "Feature: X\n"
        "  Rule: r1\n"
        "    Background:\n"
        "      Given setup\n"
        "    Scenario: s\n"
        "      Then ok\n"
    )
    feat = parse_feature_official(text, path="rb.feature")
    rule = feat.rules[0]
    assert rule.background is not None
    assert rule.background.steps[0].text == "setup"
    assert len(rule.scenarios) == 1


def test_parse_official_missing_extra_raises_clear_error(monkeypatch) -> None:
    import specmason.gherkin.official as mod

    monkeypatch.setattr(mod, "_HAS_GHERKIN", False)
    with pytest.raises(GherkinParseError) as exc:
        mod.parse_feature_official("Feature: X\n", path="x.feature")
    assert "gherkin-official" in exc.value.message
    assert "pip install" in exc.value.message


def test_parse_official_syntax_error_maps_to_sml003() -> None:
    from specmason.gherkin.official import parse_feature_official

    with pytest.raises(GherkinParseError) as exc:
        parse_feature_official("not valid gherkin", path="bad.feature")
    assert exc.value.code == SML003_INVALID_FEATURE_SYNTAX


def test_parse_official_no_feature_raises() -> None:
    from specmason.gherkin.official import parse_feature_official

    # gherkin-official returns empty dict for empty input
    feat = parse_feature_official("", path="empty.feature")
    # An empty feature is returned (name="", no scenarios)
    assert feat.name == ""


def test_parse_official_expand_scenarios() -> None:
    from specmason.gherkin.model import expand_scenarios
    from specmason.gherkin.official import parse_feature_official

    text = (
        "Feature: X\n"
        "  Scenario Outline: test <x>\n"
        "    Given <x>\n"
        "    Examples:\n"
        "      | x |\n"
        "      | a |\n"
        "      | b |\n"
        "      | c |\n"
    )
    feat = parse_feature_official(text, path="ex.feature")
    expanded = expand_scenarios(feat)
    assert len(expanded) == 3
    assert expanded[0].row_values == (("x", "a"),)
    assert expanded[1].row_values == (("x", "b"),)
    assert expanded[2].row_values == (("x", "c"),)
    assert expanded[0].outline_row_index == 0
    assert expanded[2].outline_row_index == 2
