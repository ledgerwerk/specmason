---
title: "SpecMason Skill"
description: Deterministic workflow for SpecMason behaviour specs, pytest mappings, coverage review, and evidence normalization.
license: Apache-2.0
compatibility: opencode
metadata:
  audience: coding-agents
  workflow: behavior-specification
---

# SpecMason Skill

Use this skill when you are asked to inspect, extend, or use the `specmason` repository, or when you need to turn behavior specifications into implementation and test work.

SpecMason is a Python CLI and library for maintaining behavior-spec artifacts, pytest mappings, reverse coverage, execution evidence, and review reports. It is diagnostic tooling. It does not own product requirements.

## Boundary

Keep this boundary intact:

```text
ReqLedger    owns requirements and acceptance criteria
SpecMason    owns behavior specs, mapping inventories, coverage, and evidence
pytest       owns executable verification
humans       approve changes to requirement truth
```

SpecMason may read ReqLedger exports, validate links, produce findings, and generate draft behavior files. It must not silently create, rewrite, or accept requirements.

Use this policy in code and documentation:

```text
ReqLedger is normative.
Code and tests are observed implementation behavior.
SpecMason is diagnostic.
Humans approve changes to requirement truth.
```

## Repository setup

From the repository root:

```bash
python -m pip install -e .
python -m pip install -e ".[dev]"
python -m pytest -q
python -m ruff check .
python -m mypy specmason
```

Runtime dependencies include `typer`, `click`, `PyYAML`, and `ledgercore>=0.2.0`. If tests fail to collect because `ledgercore` is missing, treat that as an environment setup blocker before changing product code.

The CLI entrypoint is:

```bash
specmason
```

The package entrypoint is:

```bash
python -m specmason
```

## Default workspace layout

SpecMason expects this layout unless `specmason.toml` overrides it:

```text
specmason.toml
specs/
  behavior/
    README.md
    manifest.json
    features/
      .../*.feature
    mappings/
      intentional-unmapped.json
    evidence/
      pytest-junit.json
    reports/
      specmason/
        coverage.md
        coverage.json
        mappings.json
        evidence.json
requirements/
  manifest.json
```

The default config file is `specmason.toml`. Prefer adding or changing config through the config loader rather than scattering hard-coded paths.

## Core commands

Use these commands when validating behavior work:

```bash
specmason init
specmason check
specmason create-gherkin --from requirements/manifest.json
specmason discover-pytest
specmason coverage --view both --show gaps
specmason mappings
specmason import-report pytest-junit path/to/junit.xml
specmason review
```

All main commands should support:

```bash
--config PATH
--json
```

Prefer machine-readable JSON for agent workflows and markdown for human review reports.

## Current Gherkin model

The current MVP parser is intentionally small and fail-closed. It supports:

- `Feature:`
- optional `Rule:` blocks
- `Scenario:` and `Example:`
- tags such as `@req-REQ-0001` and `@ac-AC-0001`
- steps using `Given`, `When`, `Then`, `And`, `But`
- descriptions on features, rules, and scenarios

It currently rejects or treats as unsupported:

- `Background:`
- `Scenario Outline:` / `Scenario Template:`
- `Examples:` tables
- step data tables
- doc strings
- wildcard `*` steps
- multiple `Feature:` blocks per file

When extending Gherkin support, preserve fail-closed behavior: unsupported syntax should produce an explicit finding or parse error with path and line number, not silent partial parsing.

## Identity rules

Scenario titles are not identity.

The binding identity is the tag pair:

```gherkin
@req-REQ-0001
@ac-AC-0001
Scenario: Reject invalid login password
  Given a registered user exists
  When the user submits an invalid password
  Then login is rejected
```

Do not infer durable identity from scenario names, test names, or file names. These are hints only.

Local feature lint should check:

- missing valid requirement tag
- missing valid acceptance-criterion tag
- duplicate scenario identity

Integrated lint may also check:

- unknown requirement IDs
- unknown criterion IDs
- accepted criteria without scenario coverage
- stale mappings from tests to removed criteria

## Mapping rules

Pytest tests map to behavior/criteria with explicit comments or inventory data. Prefer inline comments only when they remain close to the test they bind.

Typical mapping comment formats:

```python
# specmason: @req-REQ-0001 @ac-AC-0001
# sm: @req-REQ-0001 @ac-AC-0001
```

A pytest nodeid is observed execution identity. A requirement/criterion tag pair is product behavior identity. Keep those concepts separate.

Do not close reverse coverage with fake scenarios. If a test is internal, obsolete, or intentionally not mapped to product behavior, use the intentional-unmapped policy.

## Brownfield policy

Brownfield projects may start with tests and no ReqLedger manifest.

In standalone mode, SpecMason may:

- initialize the workspace
- parse and lint local feature files
- discover pytest tests without importing modules
- parse mapping comments
- report unmapped, mapped, and waived tests
- import pytest JUnit evidence by nodeid
- generate coverage and evidence reports

In standalone mode, SpecMason cannot verify whether a requirement or criterion exists. It should emit an informational diagnostic rather than failing unless the user explicitly configured a missing requirements manifest.

Classify unmapped tests as one of:

```text
product behavior        -> create or link a ReqLedger criterion after review
internal implementation -> waive with intentional-unmapped policy
obsolete/misleading     -> remove or rewrite
unclear                 -> keep as a review gap
```

## Integrated ReqLedger mode

Integrated mode starts from a ReqLedger JSON export, usually:

```text
requirements/manifest.json
```

SpecMason may validate that:

- `@req-*` IDs exist
- `@ac-*` IDs exist
- criterion IDs belong to the referenced requirement
- mapped criteria are accepted behavior criteria
- accepted behavior criteria have Gherkin scenario coverage
- accepted behavior criteria have pytest mapping coverage
- mapped tests have execution evidence when evidence has been imported

SpecMason must not import ReqLedger as a Python dependency. Read the exported JSON contract instead.

## Agent workflow for normal SpecMason changes

1. Inspect the task and identify which layer is affected: config, Gherkin parsing, lint, mappings, pytest discovery, coverage, evidence, review, CLI, or docs.
2. Add or update tests first. Use the existing test cluster that matches the layer.
3. Implement the smallest product change that satisfies the tests.
4. Run targeted tests, then the full suite.
5. Run lint and type checks when dependencies are available.
6. Update README or this `SKILL.md` when behavior or agent workflow changes.

Prefer small, explicit dataclasses and pure functions. Avoid global mutable state. Preserve JSON output stability unless intentionally changing a public contract.

## Agent workflow for pyepubcheck / EPUBCheck reimplementation

The goal is to use imported EPUBCheck `.feature` files as an executable specification corpus for a Python `pyepubcheck` library.

Start by improving SpecMason before implementing EPUB validation logic:

1. Ensure the packed/imported corpus includes `**/*.feature` files. If a context pack omits `.feature`, fix the pack configuration first.
2. Add a Gherkin corpus inventory command or library function that lists features, scenarios, tags, fixtures, and unsupported constructs.
3. Extend the parser to cover the Gherkin constructs used by EPUBCheck features, especially `Background`, `Scenario Outline`, `Examples`, data tables, and doc strings.
4. Add a step-vocabulary extractor that groups repeated `Given/When/Then` phrases and counts usage.
5. Add fixture discovery that resolves feature-relative files under `specs/behavior/features/**/files/**`.
6. Add a generator that converts parsed scenarios into pending pytest tests for `pyepubcheck`.
7. Implement validators in priority order: container/mimetype/package basics, OPF metadata and manifest, navigation document checks, XHTML/XML parsing, resource resolution, CSS checks, profile-specific checks.
8. For every implemented behavior, bind the pytest test to the originating scenario and keep unsupported steps visible as gaps.

Do not attempt a broad one-shot port of EPUBCheck. Use the features as a backlog and coverage map.

Recommended first report for EPUBCheck corpus work:

```text
feature_count
scenario_count
scenario_outline_count
background_count
data_table_count
doc_string_count
unique_step_pattern_count
fixture_file_count
message_id_count
unsupported_constructs_by_file
```

## Testing strategy

Use existing tests as the style guide:

```text
tests/test_config.py
tests/test_gherkin_parser.py
tests/test_gherkin_lint.py
tests/test_gherkin_writer.py
tests/test_mappings.py
tests/test_pytest_discovery.py
tests/test_coverage.py
tests/test_evidence.py
tests/test_review.py
tests/test_cli.py
```

When adding parser support, add fixtures that prove both accepted syntax and rejected malformed syntax. Every parse error should include a stable error code, source path, and line number.

When adding CLI output, test both human output and `--json` output.

When adding coverage behavior, test both directions:

```text
requirement/criterion -> feature/scenario/test/evidence
test nodeid           -> mapped criterion or intentional-unmapped waiver
```

## Reporting rules

Findings should be precise and actionable. Include:

- stable code
- severity
- location
- short message
- optional remediation hint when useful

Markdown reports should be useful for humans. JSON reports should be stable for agents.

Do not hide gaps. A gap is useful product information.

## Code style

- Python 3.10+.
- Type annotations are expected.
- Keep public dataclasses simple and serializable.
- Prefer explicit errors over implicit fallback behavior.
- Prefer `pathlib.Path` for paths.
- Keep parser behavior deterministic.
- Avoid importing test modules during pytest discovery.
- Preserve existing public command names and config keys unless a migration is included.

## Safe defaults

When uncertain:

- report a warning or gap instead of silently accepting ambiguous data;
- avoid changing requirements;
- avoid inventing IDs;
- avoid deleting user artifacts;
- write generated reports under `specs/behavior/reports/specmason/`;
- keep generated draft specs reviewable rather than authoritative.
