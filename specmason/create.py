"""Draft Gherkin generation from accepted ReqLedger behavior criteria.

``create gherkin`` reads accepted criteria with ``verification = "behavior"``
and writes deterministic draft ``.feature`` files tagged ``@req-* @ac-*
@needs-review``. Generated content is a starting point for human review; it must
not satisfy coverage on its own (SML019 is informational).

File writes use :func:`ledgercore.atomic.atomic_write_text`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ledgercore.atomic import atomic_write_text
from ledgercore.io import ensure_dir

from specmason.gherkin.model import Feature
from specmason.gherkin.writer import (
    build_feature_for_criterion,
    feature_filename_for,
    render_feature,
)
from specmason.requirements import Requirement, RequirementsIndex

FeatureStatus = str  # "created" | "skipped" | "overwritten" | "planned"


@dataclass(frozen=True)
class GeneratedFeature:
    """A single generated draft feature outcome."""

    path: str
    req_id: str
    ac_id: str
    title: str
    status: FeatureStatus

    def to_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "req_id": self.req_id,
            "ac_id": self.ac_id,
            "title": self.title,
            "status": self.status,
        }


@dataclass(frozen=True)
class GenerationResult:
    """Outcome of a draft-feature generation run."""

    features: tuple[GeneratedFeature, ...] = ()
    area: str = ""
    dry_run: bool = False
    features_dir: str = ""
    errors: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, object]:
        return {
            "features": [f.to_dict() for f in self.features],
            "area": self.area,
            "dry_run": self.dry_run,
            "features_dir": self.features_dir,
            "errors": list(self.errors),
        }


def requirement_matches_area(requirement: Requirement, area: str) -> bool:
    """Return True when ``area`` matches a requirement's tags or kind.

    Case-insensitive exact match against tags, else against ``kind``.
    """
    target = area.strip().lower()
    if not target:
        return True
    if target in {t.lower() for t in requirement.tags}:
        return True
    return requirement.kind.lower() == target


def select_accepted_behavior_criteria(
    index: RequirementsIndex, *, area: str | None = None
) -> list[tuple[Requirement, str, str]]:
    """Return ``(requirement, ac_id, statement)`` for accepted behavior criteria.

    Optionally filtered by ``area``.
    """
    area_token = area or ""
    selected: list[tuple[Requirement, str, str]] = []
    for req in sorted(index.requirements, key=lambda r: r.id):
        if area_token and not requirement_matches_area(req, area_token):
            continue
        for crit in sorted(req.criteria, key=lambda c: c.id):
            if crit.id in index.accepted_behavior_ac_ids:
                selected.append((req, crit.id, crit.statement))
    return selected


def generate_features(
    index: RequirementsIndex,
    features_dir: Path | str,
    *,
    area: str | None = None,
    force: bool = False,
    dry_run: bool = False,
) -> GenerationResult:
    """Generate draft feature files for accepted behavior criteria."""
    out_dir = Path(features_dir)
    if not dry_run:
        ensure_dir(out_dir)

    selected = select_accepted_behavior_criteria(index, area=area)
    generated: list[GeneratedFeature] = []
    errors: list[str] = []

    for req, ac_id, statement in selected:
        feature: Feature = build_feature_for_criterion(
            req_id=req.id,
            ac_id=ac_id,
            title=req.title or f"{req.id} {ac_id}",
            statement=statement or ac_id,
        )
        filename = feature_filename_for(req.id, ac_id, title=req.title)
        path = out_dir / filename
        if dry_run:
            status: FeatureStatus = "planned"
        else:
            existed = path.is_file()
            if existed and not force:
                status = "skipped"
            else:
                ensure_dir(path.parent)
                atomic_write_text(path, render_feature(feature))
                status = "overwritten" if (existed and force) else "created"
        generated.append(
            GeneratedFeature(
                path=str(path),
                req_id=req.id,
                ac_id=ac_id,
                title=req.title,
                status=status,
            )
        )

    return GenerationResult(
        features=tuple(generated),
        area=area or "",
        dry_run=dry_run,
        features_dir=str(out_dir),
        errors=tuple(errors),
    )


__all__ = [
    "GeneratedFeature",
    "GenerationResult",
    "generate_features",
    "requirement_matches_area",
    "select_accepted_behavior_criteria",
]
