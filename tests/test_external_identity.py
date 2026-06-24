"""Tests for the external identity module."""

from __future__ import annotations

from pathlib import Path

from specmason.external_identity import (
    build_identity_manifest,
    write_manifest,
)
from specmason.gherkin.official import parse_feature_official


def _make_feature(src: str, path: str = "test.feature"):
    return parse_feature_official(src, path=path)


SAMPLE_SRC = """\
Feature: Package

  Scenario: valid package
    Given ok

  Scenario Outline: invalid <kind>
    Given file "<file>"
    Examples:
      | kind   | file         |
      | missing | missing.opf |
      | empty   | empty.opf   |
"""


def test_identity_reproducibility(tmp_path: Path) -> None:
    feat = _make_feature(SAMPLE_SRC, path="epub3/package.feature")
    texts = {"epub3/package.feature": SAMPLE_SRC}
    m1, _ = build_identity_manifest([feat], namespace="EPUBCHECK", feature_texts=texts)
    m2, _ = build_identity_manifest([feat], namespace="EPUBCHECK", feature_texts=texts)
    assert m1.to_json() == m2.to_json(), "Manifest not reproducible"


def test_identity_line_move_stability(tmp_path: Path) -> None:
    feat1 = _make_feature(SAMPLE_SRC, path="epub3/package.feature")
    moved_src = "\n\n\n" + SAMPLE_SRC
    feat2 = _make_feature(moved_src, path="epub3/package.feature")
    texts1 = {"epub3/package.feature": SAMPLE_SRC}
    texts2 = {"epub3/package.feature": moved_src}
    m1, _ = build_identity_manifest(
        [feat1], namespace="EPUBCHECK", feature_texts=texts1
    )
    m2, _ = build_identity_manifest(
        [feat2], namespace="EPUBCHECK", feature_texts=texts2
    )
    ids1 = {item.id for item in m1.items}
    ids2 = {item.id for item in m2.items}
    assert ids1 == ids2, "IDs changed after line move"


def test_identity_duplicate_detection() -> None:
    src = """\
Feature: Dup
  Scenario: dup1
    Given ok
  Scenario: dup1
    Given ok
"""
    feat = _make_feature(src, path="dup.feature")
    _, findings = build_identity_manifest([feat], namespace="EPUBCHECK")
    assert len(findings) == 1
    assert "Duplicate" in findings[0].message


def test_identity_repeated_titles_with_distinct_steps_are_unique() -> None:
    src = """\
Feature: Dup
  Scenario: repeated title
    Given first path
  Scenario: repeated title
    Given second path
"""
    feat = _make_feature(src, path="dup.feature")
    manifest, findings = build_identity_manifest([feat], namespace="EPUBCHECK")
    assert len(findings) == 0
    assert len(manifest.items) == 2
    assert manifest.items[0].id != manifest.items[1].id


def test_identity_explicit_tag() -> None:
    src = """\
Feature: Tagged
  @MYTAG-12345
  Scenario: tagged scenario
    Given ok
"""
    feat = _make_feature(src, path="tagged.feature")
    manifest, findings = build_identity_manifest([feat], namespace="MYTAG")
    assert len(findings) == 0
    assert len(manifest.items) == 1
    assert manifest.items[0].id == "MYTAG-12345"


def test_identity_expanded_scenarios() -> None:
    src = """\
Feature: Expand
  Scenario Outline: test <x>
    Given <x>
    Examples:
      | x |
      | a |
      | b |
"""
    feat = _make_feature(src, path="expand.feature")
    manifest, findings = build_identity_manifest([feat], namespace="EPUBCHECK")
    assert len(findings) == 0
    assert len(manifest.items) == 2
    assert manifest.items[0].examples_row == {"x": "a"}
    assert manifest.items[1].examples_row == {"x": "b"}
    assert manifest.items[0].id != manifest.items[1].id


def test_identity_duplicate_example_rows_in_distinct_blocks_are_unique() -> None:
    src = """\
Feature: Expand
  Scenario Outline: test <x>
    Given <x>
    Examples:
      | x |
      | a |
    Examples: second block
      | x |
      | a |
"""
    feat = _make_feature(src, path="expand.feature")
    manifest, findings = build_identity_manifest([feat], namespace="EPUBCHECK")
    assert len(findings) == 0
    assert len(manifest.items) == 2
    assert manifest.items[0].id != manifest.items[1].id


def test_identity_manifest_json_roundtrip(tmp_path: Path) -> None:
    feat = _make_feature(SAMPLE_SRC, path="epub3/package.feature")
    texts = {"epub3/package.feature": SAMPLE_SRC}
    manifest, _ = build_identity_manifest(
        [feat], namespace="EPUBCHECK", feature_texts=texts
    )
    out = tmp_path / "manifest.json"
    write_manifest(manifest, out)
    content = out.read_text(encoding="utf-8")
    assert '"schema_version": 1' in content
    assert '"namespace": "EPUBCHECK"' in content
    assert manifest.to_json() == content
