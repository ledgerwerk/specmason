"""Tests for review orchestration (check + coverage + evidence + reports)."""

from __future__ import annotations

import json
from pathlib import Path

from specmason.config import load_config
from specmason.errors import SML006_MISSING_AC_TAG
from specmason.init import init_workspace
from specmason.requirements import Criterion, Requirement, build_index


def _write_feature(root: Path, name: str, body: str) -> None:
    path = root / "specs" / "behavior" / "features" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def _write_test(root: Path, name: str, body: str) -> None:
    path = root / "tests" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def _enable_external_corpus_mode(root: Path) -> None:
    config_path = root / "specmason.toml"
    text = config_path.read_text(encoding="utf-8")
    text = text.replace("require_req_tag = true", "require_req_tag = false")
    text = text.replace("require_ac_tag = true", "require_ac_tag = false")
    text = text.replace("official_parser = false", "official_parser = true")
    config_path.write_text(text, encoding="utf-8")


def _index() -> object:
    req = Requirement(
        id="REQ-0001",
        title="Login",
        kind="functional",
        status="accepted",
        priority="must",
        criteria=(
            Criterion(
                id="AC-0001",
                statement="reject invalid password",
                verification="behavior",
                status="accepted",
            ),
        ),
    )
    return build_index([req])


def test_review_writes_reports(tmp_path: Path) -> None:
    from specmason.review import run_review

    init_workspace(tmp_path)
    _write_feature(
        tmp_path,
        "login.feature",
        (
            "Feature: Login\n"
            "  @req-REQ-0001 @ac-AC-0001\n"
            "  Scenario: Reject invalid password\n"
            "    Then login is rejected\n"
        ),
    )
    _write_test(
        tmp_path,
        "test_login.py",
        "# specmason: req=REQ-0001 ac=AC-0001\ndef test_reject():\n    pass\n",
    )
    req_dir = tmp_path / "requirements"
    req_dir.mkdir(exist_ok=True)
    manifest = req_dir / "manifest.json"
    manifest.write_text(
        '{"schema_version":1,"tool":"reqledger","requirements":[{"id":"REQ-0001",'
        '"title":"Login","kind":"functional","status":"accepted","priority":"must",'
        '"criteria":[{"id":"AC-0001","statement":"reject invalid password",'
        '"verification":"behavior","status":"accepted","tags":[]}]}]}',
        encoding="utf-8",
    )
    cfg = load_config(start=tmp_path, requirements_override=str(manifest))
    result = run_review(cfg, index=_index())  # type: ignore[arg-type]

    assert any("coverage.md" in p for p in result.reports_written)
    assert any("coverage.json" in p for p in result.reports_written)
    assert any("mappings.json" in p for p in result.reports_written)

    coverage_json = cfg.reports_state_dir / "coverage.json"
    data = json.loads(coverage_json.read_text())
    assert data["mode"] == "integrated"
    assert isinstance(data["forward"], list)


def test_review_reports_lint_errors(tmp_path: Path) -> None:
    from specmason.review import run_review

    init_workspace(tmp_path)
    _write_feature(
        tmp_path,
        "login.feature",
        "Feature: Login\n  Scenario: No tags\n    Then ok\n",
    )
    cfg = load_config(start=tmp_path)
    result = run_review(cfg, index=_index())  # type: ignore[arg-type]
    assert result.has_errors
    codes = [f.code for f in result.findings]
    assert SML006_MISSING_AC_TAG in codes


def test_review_in_standalone_mode(tmp_path: Path) -> None:
    from specmason.review import run_review

    init_workspace(tmp_path)
    _write_feature(
        tmp_path,
        "login.feature",
        (
            "Feature: Login\n"
            "  @req-REQ-0001 @ac-AC-0001\n"
            "  Scenario: Reject invalid password\n"
            "    Then ok\n"
        ),
    )
    cfg = load_config(start=tmp_path)
    assert cfg.is_standalone
    result = run_review(cfg, index=None)
    # standalone doesn't require authority, coverage is mapped
    assert result.coverage is not None
    assert result.coverage.mode == "standalone"


def test_review_uses_official_parser_when_enabled(tmp_path: Path) -> None:
    from specmason.review import run_review

    init_workspace(tmp_path)
    _enable_external_corpus_mode(tmp_path)
    _write_feature(
        tmp_path,
        "login.feature",
        (
            "Feature: Login\n"
            "  Background:\n"
            "    Given a registered user exists\n"
            "\n"
            "  @req-REQ-0001 @ac-AC-0001\n"
            "  Scenario: Reject invalid password\n"
            "    Then login is rejected\n"
        ),
    )
    _write_test(
        tmp_path,
        "test_login.py",
        "# specmason: req=REQ-0001 ac=AC-0001\ndef test_reject():\n    pass\n",
    )
    req_dir = tmp_path / "requirements"
    req_dir.mkdir(exist_ok=True)
    manifest = req_dir / "manifest.json"
    manifest.write_text(
        '{"schema_version":1,"tool":"reqledger","requirements":[{"id":"REQ-0001",'
        '"title":"Login","kind":"functional","status":"accepted","priority":"must",'
        '"criteria":[{"id":"AC-0001","statement":"reject invalid password",'
        '"verification":"behavior","status":"accepted","tags":[]}]}]}',
        encoding="utf-8",
    )
    cfg = load_config(start=tmp_path, requirements_override=str(manifest))
    result = run_review(cfg, index=_index())  # type: ignore[arg-type]

    assert not any(f.code == "SML004" for f in result.findings)
    assert result.coverage is not None
    by_ac = {item.ac_id: item.status for item in result.coverage.forward}
    assert by_ac["AC-0001"] == "mapped"
