"""Tests for draft Gherkin generation from accepted behavior criteria."""

from __future__ import annotations

from pathlib import Path

from specmason.create import (
    generate_features,
    requirement_matches_area,
    select_accepted_behavior_criteria,
)
from specmason.requirements import Criterion, Requirement, build_index


def _index() -> object:
    req1 = Requirement(
        id="REQ-0001",
        title="Login",
        kind="functional",
        status="accepted",
        priority="must",
        tags=("auth",),
        criteria=(
            Criterion(
                id="AC-0001",
                statement="reject invalid password",
                verification="behavior",
                status="accepted",
            ),
            Criterion(
                id="AC-0002",
                statement="audit log",
                verification="inspection",
                status="accepted",
            ),
        ),
    )
    req2 = Requirement(
        id="REQ-0002",
        title="Profile",
        kind="functional",
        status="accepted",
        priority="should",
        tags=("profile",),
        criteria=(
            Criterion(
                id="AC-0003",
                statement="view profile",
                verification="behavior",
                status="accepted",
            ),
        ),
    )
    return build_index([req1, req2])


def test_select_only_accepted_behavior_criteria() -> None:
    selected = select_accepted_behavior_criteria(_index())  # type: ignore[arg-type]
    ac_ids = [ac_id for _, ac_id, _ in selected]
    assert ac_ids == ["AC-0001", "AC-0003"]


def test_area_filter_matches_tags() -> None:
    selected = select_accepted_behavior_criteria(_index(), area="auth")  # type: ignore[arg-type]
    assert [ac_id for _, ac_id, _ in selected] == ["AC-0001"]


def test_requirement_matches_area_case_insensitive() -> None:
    req = Requirement(
        id="REQ-0001", title="t", kind="Functional", status="accepted", priority="must"
    )
    assert requirement_matches_area(req, "functional")
    assert not requirement_matches_area(req, "auth")


def test_generate_creates_deterministic_drafts(tmp_path: Path) -> None:
    result = generate_features(_index(), tmp_path / "features")  # type: ignore[arg-type]
    assert (tmp_path / "features" / "req-0001-ac-0001.feature").is_file()
    assert (tmp_path / "features" / "req-0002-ac-0003.feature").is_file()
    assert len(result.features) == 2
    assert {f.status for f in result.features} == {"created"}
    content = (tmp_path / "features" / "req-0001-ac-0001.feature").read_text()
    assert "@req-REQ-0001" in content
    assert "@ac-AC-0001" in content
    assert "@needs-review" in content


def test_generate_is_deterministic(tmp_path: Path) -> None:
    a = generate_features(_index(), tmp_path / "a")  # type: ignore[arg-type]
    b = generate_features(_index(), tmp_path / "b")  # type: ignore[arg-type]
    for fa, fb in zip(a.features, b.features, strict=True):
        ta = Path(fa.path).read_text()
        tb = Path(fb.path).read_text()
        assert ta == tb


def test_generate_does_not_overwrite_without_force(tmp_path: Path) -> None:
    features_dir = tmp_path / "features"
    generate_features(_index(), features_dir)  # type: ignore[arg-type]
    target = features_dir / "req-0001-ac-0001.feature"
    target.write_text("# manual\n", encoding="utf-8")
    result = generate_features(_index(), features_dir)  # type: ignore[arg-type]
    statuses = {f.ac_id: f.status for f in result.features}
    assert statuses["AC-0001"] == "skipped"
    assert target.read_text() == "# manual\n"


def test_generate_force_overwrites(tmp_path: Path) -> None:
    features_dir = tmp_path / "features"
    generate_features(_index(), features_dir)  # type: ignore[arg-type]
    result = generate_features(_index(), features_dir, force=True)  # type: ignore[arg-type]
    statuses = {f.ac_id: f.status for f in result.features}
    assert statuses["AC-0001"] == "overwritten"


def test_generate_dry_run_writes_nothing(tmp_path: Path) -> None:
    features_dir = tmp_path / "features"
    result = generate_features(_index(), features_dir, dry_run=True)  # type: ignore[arg-type]
    assert all(f.status == "planned" for f in result.features)
    assert not features_dir.exists()
