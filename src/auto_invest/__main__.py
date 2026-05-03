"""Entrypoint for `python -m auto_invest`.

Delegates to the Typer CLI so the operator can choose between the
console script (`auto-invest`) and the module form interchangeably.
"""

from auto_invest.cli import app

if __name__ == "__main__":
    app()
