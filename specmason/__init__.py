"""SpecMason: Ledgerwerk behavior/specification builder, checker, and reconciler.

SpecMason is the builder, checker, and reconciliation tool for behavior
artifacts. It connects accepted requirements (owned by ReqLedger) to concrete
behavior examples (Gherkin), pytest tests, mapping inventories, coverage
reports, and execution evidence.

SpecMason depends on :mod:`ledgercore` for generic storage/ledger primitives
(atomic IO, deterministic JSON, config and path resolution, prefixed IDs, ref
parsing, hashing, and timestamps). It never imports ReqLedger at runtime; it
only reads ReqLedger export JSON.
"""

from __future__ import annotations

try:
    from specmason._version import __version__
except Exception:  # pragma: no cover - fallback when _version.py absent
    __version__ = "0.0.0+unknown"

__all__ = ["__version__"]
