"""AST-based pytest discovery without importing test modules.

Walks Python files under ``tests_dir`` with :mod:`ast`, collecting functions
named ``test_*`` and methods of classes named ``Test*``. Each discovered test
carries the raw comment lines immediately preceding it (mapping/waiver comments
are parsed by :mod:`specmason.mappings`). No test module is ever imported.

Node ids mirror pytest's ``file::[Class::]function`` format, sorted by node id.
File reading uses :func:`ledgercore.io.read_text`.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from ledgercore.io import read_text


@dataclass(frozen=True)
class DiscoveredTest:
    """A pytest test discovered by AST scanning."""

    nodeid: str
    file: str
    name: str
    class_name: str
    lineno: int
    preceding_comments: tuple[str, ...]


def _is_test_function(node: ast.AST) -> bool:
    return isinstance(
        node, (ast.FunctionDef, ast.AsyncFunctionDef)
    ) and node.name.startswith("test_")


def _start_line(func: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    """Earliest source line of a function including its decorators."""
    return func.lineno


def _preceding_comments(source_lines: list[str], start_line: int) -> tuple[str, ...]:
    """Return contiguous comment lines immediately above ``start_line``.

    Blank lines break the comment block. Lines are 1-indexed in ``source_lines``.
    Also looks for comments above decorators.
    """
    comments: list[str] = []
    index = start_line - 1  # convert to 0-indexed; line above the start
    while index >= 1:
        line = source_lines[index - 1]
        stripped = line.strip()
        if stripped.startswith("#"):
            comments.append(line.rstrip())
            index -= 1
            continue
        # Skip decorators to find comments above them
        if stripped.startswith("@"):
            index -= 1
            continue
        break
    comments.reverse()
    return tuple(comments)


def _discover_in_tree(
    path: Path,
    source_lines: list[str],
    tree: ast.Module,
    *,
    file_part: str,
) -> Iterator[DiscoveredTest]:
    for node in tree.body:
        if _is_test_function(node):
            yield _make_test(node, file_part, class_name="", source_lines=source_lines)
        elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            for child in node.body:
                if _is_test_function(child):
                    yield _make_test(
                        child,
                        file_part,
                        class_name=node.name,
                        source_lines=source_lines,
                    )


def _make_test(
    func: ast.FunctionDef | ast.AsyncFunctionDef,
    file_part: str,
    *,
    class_name: str,
    source_lines: list[str],
) -> DiscoveredTest:
    suffix = f"::{class_name}::{func.name}" if class_name else f"::{func.name}"
    return DiscoveredTest(
        nodeid=f"{file_part}{suffix}",
        file=file_part,
        name=func.name,
        class_name=class_name,
        lineno=func.lineno,
        preceding_comments=_preceding_comments(source_lines, _start_line(func)),
    )


def discover_tests(
    tests_dir: Path | str,
    *,
    root: Path | str | None = None,
) -> list[DiscoveredTest]:
    """Discover pytest tests under ``tests_dir`` via AST, sorted by node id."""
    base = Path(tests_dir)
    root_path = Path(root) if root is not None else base.parent

    discovered: list[DiscoveredTest] = []
    if not base.is_dir():
        return discovered

    for path in sorted(base.rglob("test_*.py")):
        try:
            text = read_text(path)
        except OSError:
            continue
        try:
            tree = ast.parse(text, filename=str(path))
        except SyntaxError:
            continue
        try:
            rel = path.relative_to(root_path)
        except ValueError:
            rel = path
        file_part = rel.as_posix()
        source_lines = text.splitlines()
        discovered.extend(
            _discover_in_tree(path, source_lines, tree, file_part=file_part)
        )

    discovered.sort(key=lambda t: t.nodeid)
    return discovered


__all__ = [
    "DiscoveredTest",
    "discover_tests",
]
