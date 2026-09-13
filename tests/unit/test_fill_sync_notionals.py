import sqlite3
from decimal import Decimal, localcontext

import pytest

from auto_invest.persistence import db
from auto_invest.persistence.fill_amounts import fill_amounts


def test_old_database_and_migration_preserve_legacy_basis(tmp_path):
    conn = db.get_connection(tmp_path / "old.db")
    conn.executescript((db.MIGRATIONS_DIR / "0001_initial.sql").read_text())
    conn.execute("INSERT INTO fills(order_correlation_id,kis_fill_id,qty,price_usd,"
                 "executed_at_utc) VALUES('old','K:1',1,'1E-8','2000-01-01')")
    before = [tuple(row) for row in conn.execute("SELECT * FROM fills")]
    assert fill_amounts(conn) == {"K:1": Decimal("0.00000001")}
    db.migrate(conn)
    assert db.migrate(conn) == []
    assert [tuple(row) for row in conn.execute("SELECT * FROM fills")] == before
    assert conn.execute("SELECT COUNT(*) FROM fill_notionals").fetchone()[0] == 0
    assert fill_amounts(conn) == {"K:1": Decimal("0.00000001")}
    conn.close()


@pytest.mark.parametrize("amount,count,average", [
    ("99.99", 1, "100"), ("100", 2, "100"),
    ("NaN", 1, "100"), ("100", 1, "Infinity"), ("-100", 1, "100"),
])
def test_corrupt_cumulative_evidence_is_not_a_legacy_fallback(tmp_path, amount, count, average):
    conn = db.get_connection(tmp_path / "t.db")
    db.migrate(conn)
    conn.execute("INSERT INTO fills(order_correlation_id,kis_fill_id,qty,price_usd,"
                 "executed_at_utc) VALUES('o','K:1',1,'100','2000-01-01')")
    conn.execute("INSERT INTO fill_notionals VALUES('K:1',?,?,?)", (amount, count, average))
    with pytest.raises(ValueError, match="FILL_NOTIONAL"):
        fill_amounts(conn)
    conn.close()


def test_amount_arithmetic_does_not_depend_on_caller_decimal_precision(tmp_path):
    conn = db.get_connection(tmp_path / "t.db")
    db.migrate(conn)
    conn.execute("INSERT INTO fills(order_correlation_id,kis_fill_id,qty,price_usd,"
                 "executed_at_utc) VALUES('o','K:3',3,'100.0133333333333333333333333',"
                 "'2000-01-01')")
    conn.execute("INSERT INTO fill_notionals VALUES('K:3','300.04',3,"
                 "'100.0133333333333333333333333')")
    # A rounded per-share value is not original cumulative amount evidence.
    with localcontext() as context:
        context.prec = 6
        with pytest.raises(ValueError, match="CUMULATIVE_MISMATCH"):
            fill_amounts(conn)
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("DELETE FROM fill_notionals")
    conn.close()
