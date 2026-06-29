"""SpecMason Typer CLI.

All commands support ``--json`` for machine-readable output. Global options
(``--version``, ``--config``) are resolved at the callback level.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import typer

from specmason import __version__
from specmason.config import load_config
from specmason.coverage import build_coverage, render_markdown
from specmason.create import generate_features
from specmason.errors import Findings
from specmason.evidence import check_evidence_against_mappings, parse_junit_xml
from specmason.gherkin.model import Feature
from specmason.init import init_workspace
from specmason.mappings import (
    MappingInventory,
    build_inventory,
    load_intentional_unmapped_policy,
)
from specmason.pytest_discovery import discover_tests
from specmason.requirements import RequirementsIndex, load_manifest
from specmason.review import run_review

app = typer.Typer(
    name="specmason",
    help=(
        "SpecMason: build, check, and reconcile behavior/specification artifacts, "
        "pytest mappings, reverse coverage, and execution evidence."
    ),
    no_args_is_help=True,
    add_completion=False,
)


# ---------------------------------------------------------------------------
# Callback
# ---------------------------------------------------------------------------


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit


@app.callback()
def main_callback(
    version: bool = typer.Option(
        None,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show the SpecMason version and exit.",
    ),
) -> None:
    """SpecMason command group."""
    return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_json(payload: dict[str, object]) -> str:
    from ledgercore.jsonio import dumps_json

    return dumps_json(payload, indent=2, sort_keys=True)


def _resolve_config(
    *,
    config: Path | None,
    requirements: str | None,
) -> object:
    cfg = load_config(config=config, requirements_override=requirements)
    return cfg


def _load_index(cfg: object) -> RequirementsIndex | None:
    from specmason.config import SpecMasonConfig

    c: SpecMasonConfig = cfg  # type: ignore[assignment]
    if c.is_integrated:
        return load_manifest(c.requirements_manifest)
    return None


def _load_inventory(cfg: object) -> MappingInventory:
    from specmason.config import SpecMasonConfig

    c: SpecMasonConfig = cfg  # type: ignore[assignment]
    waivers, _ = load_intentional_unmapped_policy(c.pytest_intentional_unmapped_policy)
    discovered = discover_tests(c.tests_dir, root=c.workspace_root)
    return build_inventory(discovered, central_waivers=waivers)


def _load_features(cfg: object) -> tuple[list[Feature], Findings]:
    from specmason.config import SpecMasonConfig
    from specmason.corpus import parse_corpus

    c: SpecMasonConfig = cfg  # type: ignore[assignment]
    if not c.features_dir.is_dir():
        return [], Findings()
    features, _, raw_findings = parse_corpus(
        c.features_dir, official_parser=c.gherkin_official_parser
    )
    return features, Findings.of(*raw_findings)


def _exit(result: dict[str, object], *, json_output: bool, errors: bool) -> None:
    if json_output:
        typer.echo(_to_json(result))
    if errors:
        raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@app.command("init")
def init_command(
    force: bool = typer.Option(False, "--force", help="Overwrite existing files."),
    json_output: bool = typer.Option(False, "--json", help="Emit JSON to stdout."),
    config: Path | None = typer.Option(
        None, "--config", help="Workspace root config path."
    ),
) -> None:
    """Initialize the SpecMason workspace layout."""
    root = config.parent.resolve() if config else Path.cwd()
    result = init_workspace(root, force=force)
    if json_output:
        typer.echo(_to_json(result.to_dict()))
        return
    typer.echo(f"Initialized SpecMason workspace at {result.root}")
    if result.created:
        typer.echo(f"created: {', '.join(result.created)}")
    if result.existing:
        typer.echo(f"existing: {', '.join(result.existing)}")
    if result.skipped:
        typer.echo(f"skipped: {', '.join(result.skipped)}")
    if result.overwritten:
        typer.echo(f"overwritten: {', '.join(result.overwritten)}")


@app.command("check")
def check_command(
    json_output: bool = typer.Option(False, "--json", help="Emit JSON to stdout."),
    config: Path | None = typer.Option(None, "--config", help="Config file path."),
    requirements: str | None = typer.Option(
        None, "--requirements", help="ReqLedger manifest path."
    ),
) -> None:
    """Validate config, features, mappings, and waivers."""
    from specmason.gherkin.lint import lint_feature_with_authority

    cfg = _resolve_config(config=config, requirements=requirements)

    from specmason.config import SpecMasonConfig

    c: SpecMasonConfig = cfg  # type: ignore[assignment]
    index = _load_index(c)
    features, findings = _load_features(c)

    for feature in features:
        findings = findings.extend(
            Findings.of(
                *lint_feature_with_authority(
                    feature,
                    known_requirement_ids=index.requirement_ids if index else None,
                    known_criterion_ids=index.criterion_ids if index else None,
                    require_req_tag=c.gherkin_require_req_tag,
                    require_ac_tag=c.gherkin_require_ac_tag,
                )
            )
        )

    waivers, policy_findings = load_intentional_unmapped_policy(
        c.pytest_intentional_unmapped_policy
    )
    combined = findings.extend(Findings.of(*policy_findings))
    errors = combined.has_errors

    result = {"findings": combined.to_list(), "has_errors": errors}
    if json_output:
        typer.echo(_to_json(result))
    else:
        for line in combined.render_lines():
            typer.echo(line)
        typer.echo(f"{len(combined)} findings ({len(combined.errors)} errors)")
    if errors:
        raise typer.Exit(code=1)


@app.command("create-gherkin")
def create_gherkin_command(
    from_manifest: str = typer.Option(
        ..., "--from", help="ReqLedger manifest JSON path."
    ),
    area: str | None = typer.Option(
        None, "--area", help="Filter requirements by area tag/kind."
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Don't write files."),
    force: bool = typer.Option(False, "--force", help="Overwrite existing files."),
    json_output: bool = typer.Option(False, "--json", help="Emit JSON to stdout."),
    config: Path | None = typer.Option(None, "--config", help="Config file path."),
) -> None:
    """Generate draft Gherkin feature files from accepted behavior criteria."""
    cfg = _resolve_config(config=config, requirements=from_manifest)
    from specmason.config import SpecMasonConfig

    c: SpecMasonConfig = cfg  # type: ignore[assignment]
    index = load_manifest(from_manifest)
    result = generate_features(
        index,
        c.features_dir,
        area=area,
        force=force,
        dry_run=dry_run,
    )
    if json_output:
        typer.echo(_to_json(result.to_dict()))
        return
    for f in result.features:
        typer.echo(f"{f.status}: {f.path}")
    typer.echo(f"{len(result.features)} features")


@app.command("discover-pytest")
def discover_pytest_command(
    json_output: bool = typer.Option(False, "--json", help="Emit JSON to stdout."),
    config: Path | None = typer.Option(None, "--config", help="Config file path."),
) -> None:
    """Discover pytest tests without importing test modules."""
    cfg = _resolve_config(config=config, requirements=None)
    from specmason.config import SpecMasonConfig

    c: SpecMasonConfig = cfg  # type: ignore[assignment]
    discovered = discover_tests(c.tests_dir, root=c.workspace_root)
    result = {"tests": [t.nodeid for t in discovered], "count": len(discovered)}
    if json_output:
        typer.echo(_to_json(result))
    else:
        for t in discovered:
            typer.echo(t.nodeid)
        typer.echo(f"{len(discovered)} tests")


@app.command("coverage")
def coverage_command(
    view: str = typer.Option("both", "--view", help="requirements|tests|both"),
    show: str = typer.Option("all", "--show", help="gaps|all"),
    requirements: str | None = typer.Option(
        None, "--requirements", help="ReqLedger manifest path."
    ),
    json_output: bool = typer.Option(False, "--json", help="Emit JSON to stdout."),
    config: Path | None = typer.Option(None, "--config", help="Config file path."),
) -> None:
    """Report requirement-to-test and test-to-requirement coverage."""
    cfg = _resolve_config(config=config, requirements=requirements)
    from specmason.config import SpecMasonConfig

    c: SpecMasonConfig = cfg  # type: ignore[assignment]
    index = _load_index(c)
    features, load_findings = _load_features(c)
    inventory = _load_inventory(c)
    report = build_coverage(features, inventory, index=index, mode=c.mode)
    report = replace(report, findings=load_findings.extend(report.findings))
    errors = report.has_errors

    if json_output:
        typer.echo(report.to_json())
    else:
        typer.echo(render_markdown(report))
    if errors:
        raise typer.Exit(code=1)


@app.command("mappings")
def mappings_command(
    json_output: bool = typer.Option(False, "--json", help="Emit JSON to stdout."),
    config: Path | None = typer.Option(None, "--config", help="Config file path."),
) -> None:
    """Show the pytest mapping inventory."""
    cfg = _resolve_config(config=config, requirements=None)
    from specmason.config import SpecMasonConfig

    c: SpecMasonConfig = cfg  # type: ignore[assignment]
    inventory = _load_inventory(c)
    if json_output:
        typer.echo(_to_json(inventory.to_dict()))
    else:
        for t in inventory.tests:
            status = t.status
            mappings = ", ".join(f"{m.req_id}/{m.ac_id}" for m in t.mappings) or "-"
            typer.echo(f"{t.nodeid}  {status}  {mappings}")


@app.command("import-report")
def import_report_command(
    format: str = typer.Argument("pytest-junit", help="Report format (pytest-junit)."),
    path: str = typer.Argument(..., help="Path to JUnit XML report."),
    json_output: bool = typer.Option(False, "--json", help="Emit JSON to stdout."),
    config: Path | None = typer.Option(None, "--config", help="Config file path."),
) -> None:
    """Import pytest JUnit XML evidence."""
    cfg = _resolve_config(config=config, requirements=None)
    from specmason.config import SpecMasonConfig

    c: SpecMasonConfig = cfg  # type: ignore[assignment]
    report = parse_junit_xml(path)
    inventory = _load_inventory(c)
    mapped_nodeids = {t.nodeid for t in inventory.tests if t.is_mapped}
    ev_findings = check_evidence_against_mappings(report, mapped_nodeids)
    errors = ev_findings.has_errors
    result = {
        "entries": [e.to_dict() for e in report.entries],
        "findings": ev_findings.to_list(),
    }
    if json_output:
        typer.echo(_to_json(result))
    else:
        for e in report.entries:
            typer.echo(f"{e.nodeid}  {e.status}  {e.time:.3f}s")
        for f in ev_findings:
            typer.echo(f.render())
    if errors:
        raise typer.Exit(code=1)


@app.command("review")
def review_command(
    json_output: bool = typer.Option(False, "--json", help="Emit JSON to stdout."),
    config: Path | None = typer.Option(None, "--config", help="Config file path."),
    requirements: str | None = typer.Option(
        None, "--requirements", help="ReqLedger manifest path."
    ),
) -> None:
    """Run check + coverage + evidence and write reports."""
    cfg = _resolve_config(config=config, requirements=requirements)
    from specmason.config import SpecMasonConfig

    c: SpecMasonConfig = cfg  # type: ignore[assignment]
    index = _load_index(c)
    result = run_review(c, index=index)
    if json_output:
        typer.echo(_to_json(result.to_dict()))
    else:
        for f in result.findings:
            typer.echo(f.render())
        typer.echo(f"reports: {', '.join(result.reports_written)}")
    if result.has_errors:
        raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# Corpus commands (external corpus mode)
# ---------------------------------------------------------------------------


corpus_app = typer.Typer(
    name="corpus",
    help="Inspect and inventory an external Gherkin corpus.",
    no_args_is_help=True,
    add_completion=False,
)
app.add_typer(corpus_app, name="corpus")


@corpus_app.command("inspect")
def corpus_inspect_command(
    json_output: bool = typer.Option(False, "--json", help="Emit JSON to stdout."),
    config: Path | None = typer.Option(None, "--config", help="Config file path."),
) -> None:
    """Inventory features, scenarios, outlines, steps, tags, fixtures, and findings."""
    cfg = _resolve_config(config=config, requirements=None)
    from specmason.config import SpecMasonConfig

    c: SpecMasonConfig = cfg  # type: ignore[assignment]
    from specmason.corpus import run_corpus_inspect

    result, findings = run_corpus_inspect(
        c.features_dir,
        official_parser=c.gherkin_official_parser,
        fixture_roots=c.external_corpus_fixture_roots,
        namespace=c.external_corpus_id_namespace,
    )
    if json_output:
        typer.echo(result.to_json())
    else:
        inv = result.inventory
        typer.echo(f"Features: {inv.feature_count}")
        typer.echo(f"Scenarios: {inv.scenario_count}")
        typer.echo(f"Outlines: {inv.outline_count}")
        typer.echo(f"Expanded examples: {inv.expanded_example_count}")
        typer.echo(f"Step patterns: {inv.step_pattern_count}")
        typer.echo(f"Steps: {inv.step_count}")
        typer.echo(f"Tags: {inv.tag_count}")
        typer.echo(f"Fixture refs: {inv.fixture_ref_count}")
        for f in findings:
            typer.echo(f.render())
    if any(f.is_error() for f in findings):
        raise typer.Exit(code=1)


@corpus_app.command("steps")
def corpus_steps_command(
    json_output: bool = typer.Option(False, "--json", help="Emit JSON to stdout."),
    config: Path | None = typer.Option(None, "--config", help="Config file path."),
) -> None:
    """Report the normalized step vocabulary."""
    cfg = _resolve_config(config=config, requirements=None)
    from specmason.config import SpecMasonConfig

    c: SpecMasonConfig = cfg  # type: ignore[assignment]
    from specmason.corpus import parse_corpus, render_steps_json, render_steps_markdown
    from specmason.gherkin.step_vocab import build_step_vocabulary

    features, _, findings = parse_corpus(
        c.features_dir, official_parser=c.gherkin_official_parser
    )
    vocab = build_step_vocabulary(features)
    if json_output:
        typer.echo(render_steps_json(vocab))
    else:
        typer.echo(render_steps_markdown(vocab))
    if any(f.is_error() for f in findings):
        raise typer.Exit(code=1)


@corpus_app.command("fixtures")
def corpus_fixtures_command(
    json_output: bool = typer.Option(False, "--json", help="Emit JSON to stdout."),
    config: Path | None = typer.Option(None, "--config", help="Config file path."),
) -> None:
    """Report extracted fixture references with resolution metadata."""
    cfg = _resolve_config(config=config, requirements=None)
    from specmason.config import SpecMasonConfig

    c: SpecMasonConfig = cfg  # type: ignore[assignment]
    from specmason.corpus import parse_corpus, render_fixtures_json

    features, _, findings = parse_corpus(
        c.features_dir, official_parser=c.gherkin_official_parser
    )
    if json_output:
        typer.echo(render_fixtures_json(features, c.external_corpus_fixture_roots))
    else:
        from specmason.fixtures import extract_fixture_refs

        for feat in features:
            for ref in extract_fixture_refs(feat, c.external_corpus_fixture_roots):
                status = "exists" if ref.exists else "MISSING"
                typer.echo(f"{feat.path}: {ref.raw} [{ref.kind}] {status}")
    if any(f.is_error() for f in findings):
        raise typer.Exit(code=1)


__all__ = ["app"]
