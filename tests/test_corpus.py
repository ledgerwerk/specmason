"""Tests for the corpus inventory and reporting module."""

from __future__ import annotations

from pathlib import Path

from specmason.corpus import (
    build_corpus_inventory,
    parse_corpus,
    render_fixtures_json,
    render_steps_json,
    render_steps_markdown,
)
from specmason.gherkin.official import parse_feature_official
from specmason.gherkin.step_vocab import build_step_vocabulary

SAMPLE_SRC = """\
# language: en
@epub3
Feature: Package

  Background:
    Given the EPUB file "test.epub" is unpacked

  Rule: valid package

    Scenario: valid package document
      Given the file "META-INF/container.xml" exists
      When the package document is parsed
      Then no errors are reported

    Scenario Outline: invalid <kind>
      Given the file "<file>" exists
      When the package document is parsed
      Then error "OPF-001" is reported
      Examples:
        | kind   | file           |
        | missing | missing.opf   |
        | empty   | empty.opf     |
"""


def _features_dir(tmp_path: Path) -> Path:
    d = tmp_path / "features"
    d.mkdir()
    (d / "sample.feature").write_text(SAMPLE_SRC, encoding="utf-8")
    return d


def test_corpus_inspect_counts(tmp_path: Path) -> None:
    feat = parse_feature_official(SAMPLE_SRC, path="features/sample.feature")
    inventory = build_corpus_inventory([feat], findings=[], fixture_roots=(tmp_path,))
    assert inventory.feature_count == 1
    assert inventory.scenario_count == 1  # 1 Scenario (outlines counted separately)
    assert inventory.outline_count == 1
    assert inventory.expanded_example_count == 2
    assert inventory.step_count > 0
    assert inventory.tag_count > 0
    assert inventory.fixture_ref_count > 0


def test_corpus_inspect_json_deterministic(tmp_path: Path) -> None:
    feat = parse_feature_official(SAMPLE_SRC, path="features/sample.feature")
    inventory = build_corpus_inventory([feat], findings=[], fixture_roots=(tmp_path,))
    j1 = inventory.to_json()
    j2 = inventory.to_json()
    assert j1 == j2, "Corpus inspect JSON not deterministic"


def test_corpus_steps_markdown_deterministic(tmp_path: Path) -> None:
    feat = parse_feature_official(SAMPLE_SRC, path="features/sample.feature")
    vocab = build_step_vocabulary([feat])
    m1 = render_steps_markdown(vocab)
    m2 = render_steps_markdown(vocab)
    assert m1 == m2, "Steps markdown not deterministic"
    assert "unique normalized step patterns" in m1


def test_corpus_steps_json_deterministic(tmp_path: Path) -> None:
    feat = parse_feature_official(SAMPLE_SRC, path="features/sample.feature")
    vocab = build_step_vocabulary([feat])
    j1 = render_steps_json(vocab)
    j2 = render_steps_json(vocab)
    assert j1 == j2, "Steps JSON not deterministic"


def test_corpus_fixtures_json_deterministic(tmp_path: Path) -> None:
    feat = parse_feature_official(SAMPLE_SRC, path="features/sample.feature")
    roots = (tmp_path / "features",)
    roots[0].mkdir(exist_ok=True)
    j1 = render_fixtures_json([feat], roots)
    j2 = render_fixtures_json([feat], roots)
    assert j1 == j2, "Fixtures JSON not deterministic"


def test_corpus_no_req_ac_tags_required(tmp_path: Path) -> None:
    """Corpus commands must not fail on external corpora without @req/@ac."""
    d = _features_dir(tmp_path)
    features, docs, findings = parse_corpus(d, official_parser=True)
    assert len(features) == 1
    assert not any(f.is_error() for f in findings)
    # The feature has no @req/@ac tags.
    feat = features[0]
    for sc in feat.all_scenarios:
        assert "@req-" not in " ".join(sc.tags)
        assert "@ac-" not in " ".join(sc.tags)


def test_corpus_parse_corpus_official(tmp_path: Path) -> None:
    d = _features_dir(tmp_path)
    features, docs, findings = parse_corpus(d, official_parser=True)
    assert len(features) == 1
    assert len(docs) == 1
    assert docs[0].feature.name == "Package"
    assert docs[0].comments == ()  # no comments in sample


def test_corpus_parse_corpus_line_parser(tmp_path: Path) -> None:
    """Line parser on a corpus with Background should produce a finding."""
    d = _features_dir(tmp_path)
    features, docs, findings = parse_corpus(d, official_parser=False)
    # Background is unsupported by line parser -> error finding.
    assert len(features) == 0
    assert len(findings) > 0
    assert any(f.code == "SML004" for f in findings)
