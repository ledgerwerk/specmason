"""Gherkin lint rules: required tags and duplicate scenario identity.

IDs are the binding authority. A scenario's identity is the ``(@req, @ac)`` pair
extracted from its tags. Candidate title matches are never bindings.

Lint focuses on local feature-file rules (SML005/SML006/SML007). Requirement and
criterion *existence* checks (SML008/SML009) belong to check/coverage and need a
ReqLedger index; see :func:`lint_feature_with_authority`.
"""

from __future__ import annotations

from specmason.errors import (
    SML005_MISSING_REQ_TAG,
    SML006_MISSING_AC_TAG,
    SML007_DUPLICATE_SCENARIO_IDENTITY,
    SML008_UNKNOWN_REQUIREMENT_ID,
    SML009_UNKNOWN_CRITERION_ID,
    Finding,
    Findings,
)
from specmason.gherkin.model import Feature
from specmason.ids import extract_identity


def lint_feature(
    feature: Feature,
    *,
    require_req_tag: bool = True,
    require_ac_tag: bool = True,
) -> Findings:
    """Lint a single feature file for tag presence and duplicate identity."""
    findings = Findings()
    seen: dict[tuple[str, str], str] = {}

    for scenario in feature.iter_scenarios():
        location = f"{feature.path}:{scenario.line}"
        req_id, ac_id = extract_identity(list(scenario.tags))

        if require_req_tag and req_id is None:
            findings = findings.append(
                Finding(
                    SML005_MISSING_REQ_TAG,
                    "error",
                    f"scenario {scenario.name!r} is missing a valid @req-REQ-NNNN tag",
                    location,
                )
            )
        if require_ac_tag and ac_id is None:
            findings = findings.append(
                Finding(
                    SML006_MISSING_AC_TAG,
                    "error",
                    f"scenario {scenario.name!r} is missing a valid @ac-AC-NNNN tag",
                    location,
                )
            )

        if req_id is not None and ac_id is not None:
            key = (req_id, ac_id)
            if key in seen:
                findings = findings.append(
                    Finding(
                        SML007_DUPLICATE_SCENARIO_IDENTITY,
                        "error",
                        (
                            f"duplicate scenario identity @req-{req_id} @ac-{ac_id} "
                            f"(first seen at {seen[key]})"
                        ),
                        location,
                    )
                )
            else:
                seen[key] = location

    return findings


def lint_feature_with_authority(
    feature: Feature,
    *,
    known_requirement_ids: set[str] | None,
    known_criterion_ids: set[str] | None,
    require_req_tag: bool = True,
    require_ac_tag: bool = True,
) -> Findings:
    """Lint a feature, additionally checking id existence when authority known.

    ``known_requirement_ids``/``known_criterion_ids`` are ``None`` in standalone
    mode (existence cannot be checked). When provided (integrated mode), unknown
    ids produce SML008/SML009.
    """
    findings = lint_feature(
        feature, require_req_tag=require_req_tag, require_ac_tag=require_ac_tag
    )

    if known_requirement_ids is None and known_criterion_ids is None:
        return findings

    req_known = known_requirement_ids if known_requirement_ids is not None else set()
    ac_known = known_criterion_ids if known_criterion_ids is not None else set()

    for scenario in feature.iter_scenarios():
        location = f"{feature.path}:{scenario.line}"
        req_id, ac_id = extract_identity(list(scenario.tags))
        req_unknown = (
            known_requirement_ids is not None
            and req_id is not None
            and req_id not in req_known
        )
        if req_unknown:
            findings = findings.append(
                Finding(
                    SML008_UNKNOWN_REQUIREMENT_ID,
                    "error",
                    (
                        f"scenario {scenario.name!r} references unknown "
                        f"requirement {req_id}"
                    ),
                    location,
                )
            )
        ac_unknown = (
            known_criterion_ids is not None
            and ac_id is not None
            and ac_id not in ac_known
        )
        if ac_unknown:
            findings = findings.append(
                Finding(
                    SML009_UNKNOWN_CRITERION_ID,
                    "error",
                    (
                        f"scenario {scenario.name!r} references unknown "
                        f"criterion {ac_id}"
                    ),
                    location,
                )
            )

    return findings


__all__ = [
    "lint_feature",
    "lint_feature_with_authority",
]
