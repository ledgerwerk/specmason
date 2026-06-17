"""Tests for JUnit XML evidence import and normalization."""

from __future__ import annotations

from pathlib import Path

from specmason.errors import (
    SML017_EVIDENCE_MISSING_MAPPED_TEST,
    SML018_EVIDENCE_FAILED_MAPPED_TEST,
)
from specmason.evidence import check_evidence_against_mappings, parse_junit_xml

JUNIT_XML = """\
<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="pytest" tests="4" errors="1" failures="1" skipped="1">
    <testcase classname="tests.test_auth" name="test_login_pass" time="0.01" />
    <testcase classname="tests.test_auth" name="test_reject_fail" time="0.02">
      <failure message="assert 1 == 0">
        assert 1 == 0
      </failure>
    </testcase>
    <testcase classname="tests.test_auth.TestSuite"
              name="test_logout_skip" time="0.003">
      <skipped message="not implemented" />
    </testcase>
    <testcase classname="tests.test_util" name="test_helper_err" time="0.001">
      <error message="RuntimeError">boom</error>
    </testcase>
    <testcase classname="tests.test_util" name="test_ok" time="0.0" />
  </testsuite>
</testsuites>
"""


def _write_junit(tmp_path: Path) -> Path:
    p = tmp_path / "junit.xml"
    p.write_text(JUNIT_XML, encoding="utf-8")
    return p


def test_parse_junit_xml(tmp_path: Path) -> None:
    report = parse_junit_xml(_write_junit(tmp_path))
    assert len(report.entries) == 5
    by_nodeid = report.by_nodeid
    assert "tests/test_auth.py::test_login_pass" in by_nodeid
    assert by_nodeid["tests/test_auth.py::test_login_pass"].status == "passed"
    assert by_nodeid["tests/test_auth.py::test_reject_fail"].status == "failed"
    skip_nodeid = "tests/test_auth.py::TestSuite::test_logout_skip"
    assert by_nodeid[skip_nodeid].status == "skipped"
    assert by_nodeid["tests/test_util.py::test_helper_err"].status == "error"
    assert by_nodeid["tests/test_util.py::test_ok"].status == "passed"


def test_junit_messages_preserved(tmp_path: Path) -> None:
    report = parse_junit_xml(_write_junit(tmp_path))
    failed = report.by_nodeid["tests/test_auth.py::test_reject_fail"]
    assert "assert 1 == 0" in failed.message
    error = report.by_nodeid["tests/test_util.py::test_helper_err"]
    assert error.message == "RuntimeError"


def test_junit_classname_for_methods(tmp_path: Path) -> None:
    report = parse_junit_xml(_write_junit(tmp_path))
    method = report.by_nodeid["tests/test_auth.py::TestSuite::test_logout_skip"]
    assert method.classname == "tests.test_auth.TestSuite"
    assert method.name == "test_logout_skip"


def test_check_evidence_missing_mapped_test(tmp_path: Path) -> None:
    report = parse_junit_xml(_write_junit(tmp_path))
    mapped = {
        "tests/test_auth.py::test_not_in_xml",
        "tests/test_auth.py::test_login_pass",
    }
    findings = check_evidence_against_mappings(report, mapped)
    assert any(f.code == SML017_EVIDENCE_MISSING_MAPPED_TEST for f in findings)


def test_check_evidence_fails_non_passed_mapped(tmp_path: Path) -> None:
    report = parse_junit_xml(_write_junit(tmp_path))
    mapped = {
        "tests/test_auth.py::test_reject_fail",
        "tests/test_auth.py::test_login_pass",
    }
    findings = check_evidence_against_mappings(report, mapped)
    assert any(f.code == SML018_EVIDENCE_FAILED_MAPPED_TEST for f in findings)


def test_check_evidence_passes_all_green(tmp_path: Path) -> None:
    report = parse_junit_xml(_write_junit(tmp_path))
    mapped = {"tests/test_auth.py::test_login_pass", "tests/test_util.py::test_ok"}
    findings = check_evidence_against_mappings(report, mapped)
    assert not findings.has_errors
