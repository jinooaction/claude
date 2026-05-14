"""`python -m auto_invest.canary` entrypoint.

Delegates to the Typer app in ``auto_invest.canary.cli`` so the
canonical canary CLI is ``python -m auto_invest.canary``.
"""

from __future__ import annotations

from auto_invest.canary.cli import main

if __name__ == "__main__":
    main()
