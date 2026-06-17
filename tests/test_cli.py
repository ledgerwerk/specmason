"""Tests for CLI commands via Typer CliRunner."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from specmason.cli import app

runner = CliRunner()


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
