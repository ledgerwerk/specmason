"""Tests for AST-based pytest discovery."""

from __future__ import annotations

from pathlib import Path

from specmason.pytest_discovery import discover_tests


def _write(root: Path, rel: str, body: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def test_discovers_functions_and_methods(tmp_path: Path) -> None:
    src = (
        "def helper():\n    pass\n\n\n"
        "def test_login():\n    pass\n\n\n"
        "class TestSuite:\n"
        "    def test_logout(self):\n        pass\n"
        "    def helper(self):\n        pass\n"
    )
    _write(tmp_path / "tests", "test_auth.py", src)
    tests = discover_tests(tmp_path / "tests", root=tmp_path)
    nodeids = [t.nodeid for t in tests]
    assert "tests/test_auth.py::test_login" in nodeids
    assert "tests/test_auth.py::TestSuite::test_logout" in nodeids
    assert all("helper" not in n for n in nodeids)
    assert nodeids == sorted(nodeids)


def test_discovers_nested_dirs_and_sorts(tmp_path: Path) -> None:
    _write(tmp_path / "tests", "z/test_b.py", "def test_b():\n    pass\n")
    _write(tmp_path / "tests", "a/test_a.py", "def test_a():\n    pass\n")
    tests = discover_tests(tmp_path / "tests", root=tmp_path)
    assert [t.name for t in tests] == ["test_a", "test_b"]


def test_does_not_import_modules(tmp_path: Path) -> None:
    # A module that would raise at import time must not be imported.
    _write(
        tmp_path / "tests",
        "test_boom.py",
        "raise RuntimeError('import side effect')\n\ndef test_x():\n    pass\n",
    )
    tests = discover_tests(tmp_path / "tests", root=tmp_path)
    # SyntaxError-free but import would fail; discovery still parses via AST.
    assert [t.name for t in tests] == ["test_x"]


def test_syntax_error_file_skipped(tmp_path: Path) -> None:
    _write(tmp_path / "tests", "test_bad.py", "def (\n")
    _write(tmp_path / "tests", "test_good.py", "def test_ok():\n    pass\n")
    tests = discover_tests(tmp_path / "tests", root=tmp_path)
    assert [t.name for t in tests] == ["test_ok"]


def test_collects_preceding_comments(tmp_path: Path) -> None:
    _write(
        tmp_path / "tests",
        "test_m.py",
        "# specmason: req=REQ-0001 ac=AC-0001\n"
        "# sm: req=REQ-0002 ac=AC-0002\n"
        "def test_mapped():\n"
        "    pass\n",
    )
    tests = discover_tests(tmp_path / "tests", root=tmp_path)
    test = next(t for t in tests if t.name == "test_mapped")
    assert len(test.preceding_comments) == 2


def test_blank_line_breaks_comment_block(tmp_path: Path) -> None:
    _write(
        tmp_path / "tests",
        "test_m.py",
        "# specmason: req=REQ-0001 ac=AC-0001\n"
        "\n"
        "def test_mapped():\n"
        "    pass\n",
    )
    tests = discover_tests(tmp_path / "tests", root=tmp_path)
    test = next(t for t in tests if t.name == "test_mapped")
    assert test.preceding_comments == ()


def test_missing_dir_returns_empty(tmp_path: Path) -> None:
    assert discover_tests(tmp_path / "nope", root=tmp_path) == []


def test_async_test_functions(tmp_path: Path) -> None:
    _write(
        tmp_path / "tests",
        "test_a.py",
        "async def test_async():\n    pass\n",
    )
    tests = discover_tests(tmp_path / "tests", root=tmp_path)
    assert [t.name for t in tests] == ["test_async"]
