"""Pytest JUnit XML evidence import and normalization.

Parses pytest JUnit XML reports, maps test cases by node id, normalizes status
to a fixed vocabulary (``passed``, ``failed``, ``skipped``, ``error``), and
serializes deterministic evidence JSON.

Stdlib ``xml.etree.ElementTree`` is used for parsing (no external dependency).
JSON output uses :func:`ledgercore.jsonio.dumps_json`. Node ids are
reconstructed from JUnit ``classname`` + ``name`` attributes to match pytest's
``file::[Class::]func`` format.

Failed, skipped, error, undefined, and missing mapped cases fail closed
(SML017/SML018).
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from specmason.errors import (
    SML017_EVIDENCE_MISSING_MAPPED_TEST,
    SML018_EVIDENCE_FAILED_MAPPED_TEST,
    Finding,
    Findings,
)

Status = Literal["passed", "failed", "skipped", "error"]


@dataclass(frozen=True)
class EvidenceEntry:
    """A single test case from JUnit XML."""

    nodeid: str
    classname: str
    name: str
    status: Status
    time: float
    message: str = ""
    output: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "nodeid": self.nodeid,
            "classname": self.classname,
            "name": self.name,
            "status": self.status,
            "time": self.time,
            "message": self.message,
            "output": self.output,
        }


@dataclass(frozen=True)
class EvidenceReport:
    """A normalized evidence report from JUnit XML."""

    entries: tuple[EvidenceEntry, ...] = ()
    by_nodeid: dict[str, EvidenceEntry] = field(default_factory=dict)
    findings: Findings = field(default_factory=Findings)

    @classmethod
    def of(
        cls, entries: list[EvidenceEntry], findings: Findings | None = None
    ) -> EvidenceReport:
        by_nodeid = {e.nodeid: e for e in entries}
        return cls(
            entries=tuple(entries),
            by_nodeid=by_nodeid,
            findings=findings or Findings(),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "entries": [e.to_dict() for e in self.entries],
            "findings": self.findings.to_list(),
        }


def _nodeid_from_junit(classname: str, name: str) -> str:
    """Reconstruct a pytest node id from JUnit classname + name.

    ``classname`` is the dotted module path (with class appended for class
    methods). ``name`` is the test function/method name.
    """
    parts = classname.split(".")
    if parts and parts[-1] and parts[-1][0].isupper():
        class_name = parts[-1]
        module_parts = parts[:-1]
    else:
        class_name = ""
        module_parts = parts
    file_path = "/".join(module_parts) + ".py"
    if class_name:
        return f"{file_path}::{class_name}::{name}"
    return f"{file_path}::{name}"


def _parse_testcase(element: ET.Element) -> EvidenceEntry:
    classname = element.get("classname", "")
    name = element.get("name", "")
    time_str = element.get("time", "0")
    try:
        time_val = float(time_str)
    except (TypeError, ValueError):
        time_val = 0.0
    nodeid = _nodeid_from_junit(classname, name)
    message = ""
    status: Status = "passed"
    for child in element:
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        if tag == "failure":
            status = "failed"
            message = child.get("message", "") or (child.text or "").strip()
        elif tag == "error":
            status = "error"
            message = child.get("message", "") or (child.text or "").strip()
        elif tag == "skipped":
            status = "skipped"
            message = child.get("message", "") or (child.text or "").strip()
    return EvidenceEntry(
        nodeid=nodeid,
        classname=classname,
        name=name,
        status=status,
        time=time_val,
        message=message,
    )


def parse_junit_xml(path: Path | str) -> EvidenceReport:
    """Parse a pytest JUnit XML report into an :class:`EvidenceReport`.

    Raises :class:`OSError` on file I/O failure and
    :class:`xml.etree.ElementTree.ParseError` on malformed XML.
    """
    tree = ET.parse(str(path))
    root = tree.getroot()
    entries: list[EvidenceEntry] = []
    for testcase in root.iter("testcase"):
        entries.append(_parse_testcase(testcase))
    entries.sort(key=lambda e: e.nodeid)
    return EvidenceReport.of(entries)


def check_evidence_against_mappings(
    report: EvidenceReport,
    mapped_nodeids: set[str],
) -> Findings:
    """Check evidence against mapped test node ids.

    SML017: mapped node id has no evidence entry.
    SML018: mapped evidence entry has a non-passed status.
    """
    findings = Findings()
    for nodeid in sorted(mapped_nodeids):
        entry = report.by_nodeid.get(nodeid)
        if entry is None:
            findings = findings.append(
                Finding(
                    SML017_EVIDENCE_MISSING_MAPPED_TEST,
                    "error",
                    f"mapped test {nodeid} has no evidence entry",
                    nodeid,
                )
            )
        elif entry.status != "passed":
            findings = findings.append(
                Finding(
                    SML018_EVIDENCE_FAILED_MAPPED_TEST,
                    "error",
                    (
                        f"mapped test {nodeid} is {entry.status}: "
                        f"{entry.message}"
                    ),
                    nodeid,
                )
            )
    return findings


__all__ = [
    "EvidenceEntry",
    "EvidenceReport",
    "check_evidence_against_mappings",
    "parse_junit_xml",
]
