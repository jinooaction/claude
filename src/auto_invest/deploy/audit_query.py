"""Audit-log read helpers for the deploy runner — spec 006 T018.

The runner uses these to (a) confirm the worker came up after a
restart and (b) detect failures during the health window.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path


def open_readonly(db_path: Path) -> sqlite3.Connection:
    """Open the audit DB read-only (sqlite URI mode=ro)."""
    uri = f"file:{db_path}?mode=ro"
    return sqlite3.connect(uri, uri=True)


def fetch_correlation(
    db_path: Path,
    correlation_id: str,
) -> list[sqlite3.Row]:
    """Return all audit rows for one correlation_id in seq order."""
    conn = open_readonly(db_path)
    try:
        conn.row_factory = sqlite3.Row
        return list(
            conn.execute(
                "SELECT * FROM audit_log WHERE correlation_id = ? ORDER BY seq",
                (correlation_id,),
            )
        )
    finally:
        conn.close()
