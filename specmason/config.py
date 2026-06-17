"""SpecMason configuration discovery and path resolution.

Config lookup order (first wins):

1. explicit ``--config`` path,
2. ``specmason.toml`` discovered upward from the current directory,
3. ``.specmason.toml`` discovered upward,
4. built-in defaults (paths relative to the current directory).

When both ``specmason.toml`` and ``.specmason.toml`` exist in the same
directory, the visible ``specmason.toml`` wins. Paths declared in config resolve
relative to the config file's directory; with no config they resolve relative to
the current working directory.

Path discovery and relative-path validation use :mod:`ledgercore.paths`
(:func:`locate_config`, :func:`find_config_upwards`,
:func:`resolve_relative_child`) so SpecMason stays consistent with the rest of
the Ledgerwerk family.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field, replace
from enum import Enum
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib as _toml
else:  # pragma: no cover - exercised only on 3.10
    import tomli as _toml

from ledgercore.paths import (
    ConfigLocator,
    find_config_upwards,
    locate_config,
    resolve_relative_child,
)

from specmason.errors import ConfigError

CONFIG_FILENAMES: tuple[str, ...] = ("specmason.toml", ".specmason.toml")
PUBLIC_CONFIG_FILENAME = "specmason.toml"
HIDDEN_CONFIG_FILENAME = ".specmason.toml"

# (attr, section, key, kind) describing every non-paths config field.
# kind ∈ {"path", "bool", "str", "int"}.
_SCALAR_FIELDS: tuple[tuple[str, str, str, str], ...] = (
    ("schema_version", "", "schema_version", "int"),
    ("requirements_required", "requirements", "required", "bool"),
    ("gherkin_default_keyword", "gherkin", "default_keyword", "str"),
    ("gherkin_require_req_tag", "gherkin", "require_req_tag", "bool"),
    ("gherkin_require_ac_tag", "gherkin", "require_ac_tag", "bool"),
    ("gherkin_allow_markdown_gherkin", "gherkin", "allow_markdown_gherkin", "bool"),
    ("gherkin_official_parser", "gherkin", "official_parser", "bool"),
    ("pytest_mapping_comment_prefix", "pytest", "mapping_comment_prefix", "str"),
    (
        "pytest_short_mapping_comment_prefix",
        "pytest",
        "short_mapping_comment_prefix",
        "str",
    ),
    (
        "pytest_intentional_unmapped_policy",
        "pytest",
        "intentional_unmapped_policy",
        "path",
    ),
)

# Path fields under [paths].
_PATH_FIELDS: tuple[tuple[str, str], ...] = (
    ("behavior_root", "behavior_root"),
    ("features_dir", "features_dir"),
    ("manifest", "manifest"),
    ("mappings_dir", "mappings_dir"),
    ("evidence_dir", "evidence_dir"),
    ("reports_dir", "reports_dir"),
    ("reports_state_dir", "reports_state_dir"),
    ("tests_dir", "tests_dir"),
)


class Mode(str, Enum):
    """Operating mode: integrated reads ReqLedger exports; standalone does not."""

    STANDALONE = "standalone"
    INTEGRATED = "integrated"


def _default_fields() -> dict[str, Any]:
    """Built-in config defaults (mirrors the MVP brief default config)."""
    return {
        "schema_version": 1,
        "paths": {
            "behavior_root": "specs/behavior",
            "features_dir": "specs/behavior/features",
            "manifest": "specs/behavior/manifest.json",
            "mappings_dir": "specs/behavior/mappings",
            "evidence_dir": "specs/behavior/evidence",
            "reports_dir": "specs/behavior/reports",
            "reports_state_dir": "specs/behavior/reports/specmason",
            "tests_dir": "tests",
        },
        "requirements": {
            "manifest": "requirements/manifest.json",
            "required": False,
        },
        "gherkin": {
            "default_keyword": "Scenario",
            "require_req_tag": True,
            "require_ac_tag": True,
            "allow_markdown_gherkin": False,
            "official_parser": False,
        },
        "pytest": {
            "mapping_comment_prefix": "specmason",
            "short_mapping_comment_prefix": "sm",
            "intentional_unmapped_policy": (
                "specs/behavior/mappings/intentional-unmapped.json"
            ),
        },
    }


def _load_toml_document(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as handle:
            return _toml.load(handle)
    except FileNotFoundError as exc:  # pragma: no cover - callers guard this
        raise ConfigError(f"Config file not found: {path}") from exc
    except _toml.TOMLDecodeError as exc:
        raise ConfigError(f"Invalid TOML in config {path}: {exc}") from exc
    except OSError as exc:
        raise ConfigError(f"Cannot read config {path}: {exc}") from exc


def _coerce_bool(value: object, *, field_name: str, default: bool) -> bool:
    if value is None:
        return default
    if not isinstance(value, bool):
        raise ConfigError(f"[{field_name}] must be a boolean")
    return value


def _coerce_int(value: object, *, field_name: str, default: int) -> int:
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(f"[{field_name}] must be an integer")
    return value


def _section(document: dict[str, Any], name: str) -> dict[str, Any]:
    section = document.get(name, {})
    if not isinstance(section, dict):
        raise ConfigError(f"[{name}] must be a table")
    return section


def _resolve_relative(base: Path, value: str, *, field_name: str) -> Path:
    """Resolve a config-declared path relative to ``base``.

    Relative POSIX paths validate and resolve under ``base`` via ledgercore;
    absolute paths are accepted as-is.
    """
    rendered = value.strip()
    if not rendered:
        raise ConfigError(f"Config path value must not be empty: {field_name}")
    candidate = Path(rendered)
    if candidate.is_absolute():
        return candidate
    return resolve_relative_child(base, rendered, field_name=field_name)


@dataclass(frozen=True)
class SpecMasonConfig:
    """Resolved SpecMason configuration.

    All path attributes are absolute and resolved relative to the config file's
    directory (or the workspace root when no config exists). ``config_path`` is
    empty when running on pure defaults.
    """

    schema_version: int
    workspace_root: Path
    config_path: Path
    behavior_root: Path
    features_dir: Path
    manifest: Path
    mappings_dir: Path
    evidence_dir: Path
    reports_dir: Path
    reports_state_dir: Path
    tests_dir: Path
    requirements_manifest: Path
    requirements_required: bool
    gherkin_default_keyword: str
    gherkin_require_req_tag: bool
    gherkin_require_ac_tag: bool
    gherkin_allow_markdown_gherkin: bool
    gherkin_official_parser: bool
    pytest_mapping_comment_prefix: str
    pytest_short_mapping_comment_prefix: str
    pytest_intentional_unmapped_policy: Path
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def default_fields(cls) -> dict[str, Any]:
        """Return the built-in default field values."""
        return _default_fields()

    @property
    def requirements_manifest_exists(self) -> bool:
        """True when the configured ReqLedger manifest file exists."""
        return self.requirements_manifest.is_file()

    @property
    def mode(self) -> Mode:
        """Operating mode derived from manifest presence."""
        return Mode.INTEGRATED if self.requirements_manifest_exists else Mode.STANDALONE

    @property
    def is_integrated(self) -> bool:
        """True in integrated mode (ReqLedger manifest present)."""
        return self.mode is Mode.INTEGRATED

    @property
    def is_standalone(self) -> bool:
        """True in standalone mode (no ReqLedger manifest)."""
        return self.mode is Mode.STANDALONE


def _scalar(
    attr: str,
    section: str,
    key: str,
    kind: str,
    *,
    source: dict[str, Any],
    defaults: dict[str, Any],
    base: Path,
) -> tuple[str, Any]:
    """Resolve one scalar/bool/str/int/path field from config or defaults."""
    default = defaults[section][key] if section else defaults[key]
    raw_default = defaults[section][key] if section else defaults[key]
    value = source.get(key, raw_default) if section else source.get(key, raw_default)
    if kind == "int":
        return attr, _coerce_int(value, field_name=key, default=int(default))
    if kind == "bool":
        return attr, _coerce_bool(value, field_name=key, default=bool(default))
    if kind == "str":
        return attr, str(value)
    if kind == "path":
        return attr, _resolve_relative(base, str(value), field_name=key)
    raise ValueError(f"unsupported kind: {kind}")  # pragma: no cover


def _resolve_config(
    config_path: Path,
    document: dict[str, Any],
    *,
    requirements_override: str | Path | None,
) -> SpecMasonConfig:
    config_dir = config_path.parent.resolve()
    defaults = _default_fields()
    sections = {
        "paths": _section(document, "paths"),
        "requirements": _section(document, "requirements"),
        "gherkin": _section(document, "gherkin"),
        "pytest": _section(document, "pytest"),
    }

    kw: dict[str, Any] = {
        "workspace_root": config_dir,
        "config_path": config_path,
    }

    for attr, key in _PATH_FIELDS:
        default = defaults["paths"][key]
        value = str(sections["paths"].get(key, default))
        kw[attr] = _resolve_relative(config_dir, value, field_name=key)

    if requirements_override is not None:
        kw["requirements_manifest"] = (
            Path(requirements_override).expanduser().resolve()
        )
    else:
        default_manifest = defaults["requirements"]["manifest"]
        value = str(sections["requirements"].get("manifest", default_manifest))
        kw["requirements_manifest"] = _resolve_relative(
            config_dir, value, field_name="requirements.manifest"
        )

    for attr, section, key, kind in _SCALAR_FIELDS:
        src = document if not section else sections[section]
        kw[attr] = _scalar(
            attr, section, key, kind, source=src, defaults=defaults, base=config_dir
        )[1]

    return SpecMasonConfig(**kw)


def _build_defaults(start: Path) -> SpecMasonConfig:
    base = start.resolve()
    d = _default_fields()
    paths_d = d["paths"]
    req_d = d["requirements"]
    gh_d = d["gherkin"]
    py_d = d["pytest"]

    def pf(key: str) -> Path:
        return (base / paths_d[key]).resolve()

    kw: dict[str, Any] = {
        "schema_version": int(d["schema_version"]),
        "workspace_root": base,
        "config_path": Path(),
        "behavior_root": pf("behavior_root"),
        "features_dir": pf("features_dir"),
        "manifest": pf("manifest"),
        "mappings_dir": pf("mappings_dir"),
        "evidence_dir": pf("evidence_dir"),
        "reports_dir": pf("reports_dir"),
        "reports_state_dir": pf("reports_state_dir"),
        "tests_dir": pf("tests_dir"),
        "requirements_manifest": (base / req_d["manifest"]).resolve(),
        "requirements_required": bool(req_d["required"]),
        "gherkin_default_keyword": str(gh_d["default_keyword"]),
        "gherkin_require_req_tag": bool(gh_d["require_req_tag"]),
        "gherkin_require_ac_tag": bool(gh_d["require_ac_tag"]),
        "gherkin_allow_markdown_gherkin": bool(gh_d["allow_markdown_gherkin"]),
        "gherkin_official_parser": bool(gh_d["official_parser"]),
        "pytest_mapping_comment_prefix": str(py_d["mapping_comment_prefix"]),
        "pytest_short_mapping_comment_prefix": str(
            py_d["short_mapping_comment_prefix"]
        ),
        "pytest_intentional_unmapped_policy": (
            base / py_d["intentional_unmapped_policy"]
        ).resolve(),
    }
    return SpecMasonConfig(**kw)


def _resolve_config_path(
    *,
    config: str | Path | None,
    start: Path,
) -> Path:
    """Return the resolved config path, or an empty path for pure defaults."""
    if config is not None:
        explicit = Path(config).expanduser()
        if not explicit.is_file():
            raise ConfigError(f"Config file not found: {explicit}")
        return explicit.resolve()

    # locate_config searches upward and prefers the earlier filename in the
    # tuple, so ``specmason.toml`` wins over ``.specmason.toml`` in the same dir.
    locator: ConfigLocator | None = locate_config(start, CONFIG_FILENAMES)
    if locator is not None and locator.config_path.is_file():
        return locator.config_path

    return Path()


def load_config(
    *,
    config: str | Path | None = None,
    start: Path | None = None,
    requirements_override: str | Path | None = None,
) -> SpecMasonConfig:
    """Load a resolved SpecMason configuration.

    Args:
        config: Explicit ``--config`` path. When provided it must exist.
        start: Directory to search from (defaults to the current directory).
        requirements_override: Explicit ``--requirements`` manifest path. When
            provided and missing, this raises :class:`ConfigError` (fail closed)
            because the user explicitly asked for integrated authority.
    """
    search_start = (start or Path.cwd()).resolve()
    config_path = _resolve_config_path(config=config, start=search_start)

    if str(config_path) == "" or str(config_path) == ".":
        built = _build_defaults(search_start)
        if requirements_override is not None:
            override = Path(requirements_override).expanduser().resolve()
            built = replace(built, requirements_manifest=override)
        _enforce_explicit_requirements(built, explicit=bool(requirements_override))
        return built

    document = _load_toml_document(config_path)
    resolved = _resolve_config(
        config_path, document, requirements_override=requirements_override
    )
    _enforce_explicit_requirements(resolved, explicit=bool(requirements_override))
    return resolved


def _enforce_explicit_requirements(cfg: SpecMasonConfig, *, explicit: bool) -> None:
    """Fail closed when the user explicitly supplied a missing requirements path.

    Also fail when ``[requirements].required = true`` and the manifest is absent.
    """
    if explicit and not cfg.requirements_manifest_exists:
        raise ConfigError(
            f"Requirements manifest not found: {cfg.requirements_manifest}"
        )
    if cfg.requirements_required and not cfg.requirements_manifest_exists:
        raise ConfigError(
            f"[requirements].required is set but manifest is missing: "
            f"{cfg.requirements_manifest}"
        )


def discover_config(*, start: Path | None = None) -> Path | None:
    """Return the discovered SpecMason config path, or ``None``."""
    search_start = (start or Path.cwd()).resolve()
    return find_config_upwards(search_start, CONFIG_FILENAMES)


__all__ = [
    "CONFIG_FILENAMES",
    "HIDDEN_CONFIG_FILENAME",
    "Mode",
    "PUBLIC_CONFIG_FILENAME",
    "SpecMasonConfig",
    "discover_config",
    "load_config",
]
