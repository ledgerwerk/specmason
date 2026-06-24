"""Tests for SpecMason configuration discovery and resolution."""

from __future__ import annotations

from pathlib import Path

import pytest

from specmason.config import Mode, load_config
from specmason.errors import ConfigError


def write_config(root: Path, body: str, name: str = "specmason.toml") -> Path:
    path = root / name
    path.write_text(body, encoding="utf-8")
    return path


def test_load_config_uses_defaults_when_none(tmp_path: Path) -> None:
    cfg = load_config(start=tmp_path)
    assert cfg.config_path == Path()
    assert cfg.is_standalone
    assert cfg.mode is Mode.STANDALONE
    assert cfg.features_dir == (tmp_path / "specs/behavior/features").resolve()
    assert (
        cfg.requirements_manifest == (tmp_path / "requirements/manifest.json").resolve()
    )
    assert cfg.gherkin_require_req_tag is True
    assert cfg.pytest_mapping_comment_prefix == "specmason"


def test_public_config_wins_over_hidden(tmp_path: Path) -> None:
    write_config(
        tmp_path,
        'schema_version = 1\n[paths]\ntests_dir = "t_hidden"\n',
        ".specmason.toml",
    )
    public = write_config(
        tmp_path,
        'schema_version = 1\n[paths]\ntests_dir = "t_public"\n',
    )
    cfg = load_config(start=tmp_path)
    assert cfg.config_path == public.resolve()
    assert cfg.tests_dir == (tmp_path / "t_public").resolve()


def test_explicit_config_overrides_discovery(tmp_path: Path) -> None:
    write_config(tmp_path, 'schema_version = 1\n[paths]\ntests_dir = "discovered"\n')
    explicit = tmp_path / "elsewhere"
    explicit.mkdir()
    write_config(
        explicit,
        'schema_version = 1\n[paths]\ntests_dir = "explicit_dir"\n',
        "my.toml",
    )
    cfg = load_config(config=explicit / "my.toml", start=tmp_path)
    assert cfg.tests_dir == (explicit / "explicit_dir").resolve()


def test_paths_resolve_relative_to_config_dir(tmp_path: Path) -> None:
    sub = tmp_path / "project"
    sub.mkdir()
    write_config(sub, 'schema_version = 1\n[paths]\nfeatures_dir = "my_feats"\n')
    cfg = load_config(start=sub)
    assert cfg.features_dir == (sub / "my_feats").resolve()


def test_integrated_mode_when_manifest_exists(tmp_path: Path) -> None:
    (tmp_path / "requirements").mkdir()
    (tmp_path / "requirements/manifest.json").write_text(
        '{"schema_version":1,"tool":"reqledger","requirements":[]}',
        encoding="utf-8",
    )
    cfg = load_config(start=tmp_path)
    assert cfg.is_integrated
    assert cfg.mode is Mode.INTEGRATED


def test_standalone_mode_when_manifest_missing(tmp_path: Path) -> None:
    cfg = load_config(start=tmp_path)
    assert cfg.is_standalone
    assert not cfg.requirements_manifest_exists


def test_explicit_missing_requirements_path_fails(tmp_path: Path) -> None:
    with pytest.raises(ConfigError):
        load_config(
            start=tmp_path,
            requirements_override=str(tmp_path / "nope" / "manifest.json"),
        )


def test_explicit_config_missing_fails(tmp_path: Path) -> None:
    with pytest.raises(ConfigError):
        load_config(config=tmp_path / "missing.toml", start=tmp_path)


def test_requirements_required_flag_enforces_manifest(tmp_path: Path) -> None:
    write_config(
        tmp_path,
        "schema_version = 1\n[requirements]\nrequired = true\n",
    )
    with pytest.raises(ConfigError):
        load_config(start=tmp_path)


def test_invalid_toml_fails(tmp_path: Path) -> None:
    write_config(tmp_path, "this is = = not toml\n")
    with pytest.raises(ConfigError):
        load_config(start=tmp_path)


def test_explicit_requirements_override_used(tmp_path: Path) -> None:
    other = tmp_path / "other_manifest.json"
    other.write_text(
        '{"schema_version":1,"tool":"reqledger","requirements":[]}',
        encoding="utf-8",
    )
    cfg = load_config(start=tmp_path, requirements_override=str(other))
    assert cfg.requirements_manifest == other.resolve()
    assert cfg.is_integrated


def test_specmason_config_is_frozen(tmp_path: Path) -> None:
    cfg = load_config(start=tmp_path)
    with pytest.raises(AttributeError):
        cfg.schema_version = 2  # type: ignore[misc]
        cfg.schema_version = 2  # type: ignore[misc]


def test_config_gherkin_profile_default(tmp_path: Path) -> None:
    cfg = load_config(start=tmp_path)
    assert cfg.gherkin_profile == "reqledger"


def test_config_external_corpus_defaults(tmp_path: Path) -> None:
    cfg = load_config(start=tmp_path)
    assert cfg.external_corpus_id_namespace == "EPUBCHECK"
    assert cfg.external_corpus_id_strategy == "path-scenario-hash"
    assert len(cfg.external_corpus_fixture_roots) == 1
    assert (
        cfg.external_corpus_fixture_roots[0]
        == (tmp_path / "specs/behavior/features").resolve()
    )
    assert "error" in cfg.external_corpus_expected_message_tags
    assert "warning" in cfg.external_corpus_expected_message_tags


def test_config_external_corpus_from_toml(tmp_path: Path) -> None:
    write_config(
        tmp_path,
        (
            "schema_version = 1\n"
            "[gherkin]\n"
            'profile = "external"\n'
            "[external_corpus]\n"
            'id_namespace = "MYNS"\n'
            'id_strategy = "path-scenario-hash"\n'
            'fixture_roots = ["my/fixtures"]\n'
            'expected_message_tags = ["error"]\n'
            "[requirements]\n"
            "required = false\n"
            "[pytest]\n"
            'mapping_comment_prefix = "specmason"\n'
            'short_mapping_comment_prefix = "sm"\n'
            'intentional_unmapped_policy = "p.json"\n'
        ),
    )
    cfg = load_config(start=tmp_path)
    assert cfg.gherkin_profile == "external"
    assert cfg.external_corpus_id_namespace == "MYNS"
    assert cfg.external_corpus_fixture_roots == ((tmp_path / "my/fixtures").resolve(),)
    assert cfg.external_corpus_expected_message_tags == ("error",)


def test_config_gherkin_defaults_unchanged(tmp_path: Path) -> None:
    """Existing gherkin defaults (require_req_tag etc.) are not changed."""
    cfg = load_config(start=tmp_path)
    assert cfg.gherkin_require_req_tag is True
    assert cfg.gherkin_require_ac_tag is True
    assert cfg.gherkin_default_keyword == "Scenario"
    assert cfg.gherkin_official_parser is False
