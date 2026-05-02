"""SQLite connection factory and migration runner.

Constitution IV requires the audit log to be append-only. The
`get_connection` helper installs the standard pragmas (WAL,
synchronous=NORMAL, foreign_keys=ON) and uses `isolation_level=None`
(autocommit) so each INSERT against an audit-style table is its own
atomic write.

The migration runner executes any `*.sql` files under
`persistence/migrations/` whose stem is not yet recorded in
`schema_migrations`. Migration files MUST use `IF NOT EXISTS` guards on
every DDL statement so a partial application is safe to retry.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def get_connection(path: str | Path) -> sqlite3.Connection:
    """Open a SQLite connection with the auto-invest standard pragmas."""
    conn = sqlite3.connect(
        str(path),
        detect_types=sqlite3.PARSE_DECLTYPES,
        isolation_level=None,
    )
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_migrations_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version        TEXT PRIMARY KEY,
            applied_at_utc TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
        )
        """
    )


def _applied_versions(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT version FROM schema_migrations").fetchall()
    return {row["version"] for row in rows}


def _migration_files(migrations_dir: Path) -> list[Path]:
    return sorted(p for p in migrations_dir.glob("*.sql") if p.is_file())


def pending_migrations(
    conn: sqlite3.Connection,
    migrations_dir: Path | None = None,
) -> list[str]:
    """Return migration versions that have not yet been applied, in order."""
    migrations_dir = migrations_dir or MIGRATIONS_DIR
    _ensure_migrations_table(conn)
    applied = _applied_versions(conn)
    return [p.stem for p in _migration_files(migrations_dir) if p.stem not in applied]


def migrate(
    conn: sqlite3.Connection,
    migrations_dir: Path | None = None,
) -> list[str]:
    """Apply every pending migration in order. Returns the applied versions."""
    migrations_dir = migrations_dir or MIGRATIONS_DIR
    _ensure_migrations_table(conn)
    applied = _applied_versions(conn)
    applied_now: list[str] = []
    for path in _migration_files(migrations_dir):
        version = path.stem
        if version in applied:
            continue
        sql = path.read_text(encoding="utf-8")
        conn.executescript(sql)
        conn.execute(
            "INSERT INTO schema_migrations(version) VALUES (?)",
            (version,),
        )
        applied_now.append(version)
        logger.info("migration applied", extra={"version": version})
    return applied_now
