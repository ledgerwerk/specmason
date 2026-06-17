"""Console-script launcher for the SpecMason Typer CLI.

This module is the ``specmason`` entry point declared in ``pyproject.toml``
(``specmason = "specmason.launcher:main"``). It is intentionally a thin shim so
the Typer application and all command logic live in :mod:`specmason.cli`.
"""

from __future__ import annotations

from specmason.cli import app


def main() -> None:
    """Run the SpecMason CLI."""
    app()


if __name__ == "__main__":
    main()
