# SpecMason

SpecMason is the Ledgerwerk tool for maintaining behavior/specification artifacts,
pytest mappings, reverse coverage, and execution evidence.

It does not own requirements. [ReqLedger](https://github.com/ledgerwerk/reqledger) owns
requirements and acceptance criteria. SpecMason reads ReqLedger exports when available
and checks whether behavior specs, tests, and evidence prove accepted criteria.

SpecMason also works standalone for Brownfield projects. Without a ReqLedger
manifest, it can discover pytest tests, validate local behavior specs, report
unmapped tests, and maintain an intentional-unmapped policy.

## Installation

```bash
pip install specmason
```

## Quickstart with ReqLedger (integrated mode)

```bash
pip install specmason
specmason init
specmason create-gherkin --from requirements/manifest.json
specmason check
specmason discover-pytest
specmason coverage --view both --show gaps
specmason review
```

## Brownfield standalone quickstart

```bash
pip install specmason
specmason init
specmason discover-pytest
specmason coverage --view tests --show gaps
```

## Commands

| Command                                    | Description                                        |
| ------------------------------------------ | -------------------------------------------------- |
| `specmason init`                           | Initialize workspace layout                        |
| `specmason check`                          | Validate features, mappings, waivers               |
| `specmason create-gherkin --from MANIFEST` | Generate draft Gherkin from accepted criteria      |
| `specmason discover-pytest`                | Discover tests without importing modules           |
| `specmason coverage`                       | Report coverage in both directions                 |
| `specmason mappings`                       | Show the mapping inventory                         |
| `specmason import-report pytest-junit XML` | Import JUnit XML evidence                          |
| `specmason review`                         | Full review: check + coverage + evidence + reports |

All commands support `--json` for machine-readable output and `--config PATH`
for explicit config resolution.

## Workspace layout

```text
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
specmason.toml
```

## Dependencies

- [typer](https://github.com/tiangolo/typer) (CLI)
- [ledgercore](https://github.com/ledgerwerk/ledgercore) (generic storage/primitive library)
- `tomli` (Python < 3.11 only; stdlib `tomllib` otherwise)

## License

Apache-2.0
