"""Tests for CLI commands via Typer CliRunner."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from specmason.cli import app

runner = CliRunner()


def _enable_external_corpus_mode(root: Path) -> None:
    config_path = root / "specmason.toml"
    text = config_path.read_text(encoding="utf-8")
    text = text.replace("require_req_tag = true", "require_req_tag = false")
    text = text.replace("require_ac_tag = true", "require_ac_tag = false")
    text = text.replace("official_parser = false", "official_parser = true")
    config_path.write_text(text, encoding="utf-8")


def _write_requirements_manifest(root: Path) -> Path:
    req_dir = root / "requirements"
    req_dir.mkdir(exist_ok=True)
    manifest = req_dir / "manifest.json"
    manifest.write_text(
        '{"schema_version":1,"tool":"reqledger","requirements":[{"id":"REQ-0001",'
        '"title":"Login","kind":"functional","status":"accepted","priority":"must",'
        '"criteria":[{"id":"AC-0001","statement":"reject invalid password",'
        '"verification":"behavior","status":"accepted","tags":[]}]}]}',
        encoding="utf-8",
    )
    return manifest


def test_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.output.strip()


def test_init_creates_layout(tmp_path: Path) -> None:
    import os

    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        result = runner.invoke(app, ["init"])
        assert result.exit_code == 0
        assert "Initialized SpecMason workspace" in result.output
        assert (tmp_path / "specmason.toml").is_file()
        assert (tmp_path / "specs" / "behavior" / "features").is_dir()
    finally:
        os.chdir(cwd)


def test_init_is_idempotent(tmp_path: Path) -> None:
    import os

    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        runner.invoke(app, ["init"])
        result = runner.invoke(app, ["init"])
        assert result.exit_code == 0
        assert "existing" in result.output
    finally:
        os.chdir(cwd)


def test_init_json(tmp_path: Path) -> None:
    import os

    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        result = runner.invoke(app, ["init", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data["created"], list)
        assert isinstance(data["existing"], list)
    finally:
        os.chdir(cwd)


def test_discover_pytest(tmp_path: Path) -> None:
    import os

    test_file = tmp_path / "tests" / "test_smoke.py"
    test_file.parent.mkdir(parents=True)
    test_file.write_text("def test_ok():\n    pass\n", encoding="utf-8")
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        result = runner.invoke(app, ["discover-pytest"])
        assert result.exit_code == 0
        assert "test_ok" in result.output
    finally:
        os.chdir(cwd)


def test_coverage_json(tmp_path: Path) -> None:
    import os

    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        result = runner.invoke(app, ["coverage", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "mode" in data
    finally:
        os.chdir(cwd)


def test_check_exits_1_on_errors(tmp_path: Path) -> None:
    import os

    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        runner.invoke(app, ["init"])
        feature = tmp_path / "specs" / "behavior" / "features" / "bad.feature"
        feature.write_text(
            "Feature: X\n  Scenario: No tags\n    Then ok\n",
            encoding="utf-8",
        )
        result = runner.invoke(app, ["check"])
        assert result.exit_code == 1
    finally:
        os.chdir(cwd)


def test_check_json_output(tmp_path: Path) -> None:
    import os

    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        runner.invoke(app, ["init"])
        result = runner.invoke(app, ["check", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "findings" in data
    finally:
        os.chdir(cwd)


def test_check_uses_official_parser_when_enabled(tmp_path: Path) -> None:
    import os

    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        runner.invoke(app, ["init"])
        _enable_external_corpus_mode(tmp_path)
        feature = tmp_path / "specs" / "behavior" / "features" / "epub.feature"
        feature.write_text(
            (
                "Feature: EPUB corpus\n"
                "  Background:\n"
                "    Given shared context\n"
                "\n"
                "  Scenario: Valid external corpus feature\n"
                "    Then parsing succeeds\n"
            ),
            encoding="utf-8",
        )
        result = runner.invoke(app, ["check", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["has_errors"] is False
    finally:
        os.chdir(cwd)


def test_coverage_uses_official_parser_when_enabled(tmp_path: Path) -> None:
    import os

    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        runner.invoke(app, ["init"])
        _enable_external_corpus_mode(tmp_path)
        feature = tmp_path / "specs" / "behavior" / "features" / "login.feature"
        feature.write_text(
            (
                "Feature: Login\n"
                "  Background:\n"
                "    Given a registered user exists\n"
                "\n"
                "  @req-REQ-0001 @ac-AC-0001\n"
                "  Scenario: Reject invalid password\n"
                "    Then login is rejected\n"
            ),
            encoding="utf-8",
        )
        test_file = tmp_path / "tests" / "test_login.py"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text(
            "# specmason: req=REQ-0001 ac=AC-0001\n"
            "def test_reject_invalid_password():\n"
            "    pass\n",
            encoding="utf-8",
        )
        manifest = _write_requirements_manifest(tmp_path)
        result = runner.invoke(
            app,
            ["coverage", "--json", "--requirements", str(manifest)],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["forward"][0]["status"] == "mapped"
    finally:
        os.chdir(cwd)
