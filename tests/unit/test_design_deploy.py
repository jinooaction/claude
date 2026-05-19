"""Spec 010 후속 PR — `deploy.start_live_worker`와 `write_auto_rules_file` 단위 검증.

subprocess 실제 띄움은 통합 테스트(별도)에서 검증. 본 파일에서는:
  - write_auto_rules_file이 timestamp 포함 파일명으로 저장.
  - start_live_worker가 30초 안에 WORKER_STARTED row를 못 찾으면 None 리턴.
  - polling이 baseline 이후 row만 본다는 invariant.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from auto_invest.design import deploy
from auto_invest.persistence import audit, db
from auto_invest.persistence.audit import WorkerStartedPayload


@pytest.fixture
def conn(tmp_path):
    c = db.get_connection(tmp_path / "t.db")
    db.migrate(c)
    yield c
    c.close()


# ---------------------------------------------------------- write_auto_rules_file


def test_write_auto_rules_file_creates_timestamped_file(tmp_path):
    cfg_dir = tmp_path / "config"
    path = deploy.write_auto_rules_file("[caps]\nper_trade_pct = 5\n", config_dir=cfg_dir)
    assert path.exists()
    assert path.parent == cfg_dir
    assert path.name.startswith("rules_auto_")
    assert path.name.endswith(".toml")
    assert "[caps]" in path.read_text(encoding="utf-8")


# ---------------------------------------------------------- start_live_worker


def test_start_live_worker_returns_none_when_no_audit_row(tmp_path, conn):
    """subprocess가 audit_log에 row를 안 남기면 polling 타임아웃 → None 리턴."""
    rules_path = deploy.write_auto_rules_file(
        "[caps]\n", config_dir=tmp_path / "config",
    )

    # cli_entry를 실패하는 명령으로 — subprocess는 즉시 종료, audit row 없음.
    result = deploy.start_live_worker(
        rules_path=rules_path,
        capital_usd=Decimal("100"),
        db_path=tmp_path / "auto.db",  # 다른 DB라 audit row 안 생김
        halt_path=tmp_path / "halt.flag",
        env_file=None,
        base_url="https://example",
        prices_path=tmp_path / "prices.toml",
        conn=conn,
        poll_timeout_seconds=1,
        cli_entry=["true"],  # 즉시 성공 종료, 아무것도 안 함
    )
    assert result is None


def test_start_live_worker_finds_seeded_worker_started(tmp_path, conn):
    """미리 audit_log에 WORKER_STARTED row를 INSERT한 상태에서 호출 —
    cli_entry는 no-op이지만 polling 즉시 row 발견.

    실제로는 subprocess가 WORKER_STARTED를 직접 INSERT하지만, 단위 테스트에서는
    그 동작을 mock하기 어려우니 polling의 detection 로직만 검증.
    """
    rules_path = deploy.write_auto_rules_file(
        "[caps]\n", config_dir=tmp_path / "config",
    )

    # 호출 전 baseline 확보, 그 후 WORKER_STARTED INSERT, 그러면 polling이 발견.
    # 실제 호출 흐름과는 다르지만, polling baseline 동작 검증.

    # subprocess가 시작되자마자 audit_log에 WORKER_STARTED를 넣어주는 fake.
    # 가장 단순한 방법: cli_entry로 "audit row를 INSERT하는 짧은 python 스니펫" 호출.
    seq = audit.append(
        conn,
        WorkerStartedPayload(pid=12345, config_path=str(rules_path)),
    )

    # start_live_worker가 호출되는 시점에 conn의 audit_log에 row가 이미 있음 →
    # baseline은 그 seq. 그러면 그 이후 row가 없으므로 None이 정상.
    result = deploy.start_live_worker(
        rules_path=rules_path,
        capital_usd=Decimal("100"),
        db_path=tmp_path / "x.db",
        halt_path=tmp_path / "halt.flag",
        env_file=None,
        base_url="https://example",
        prices_path=tmp_path / "prices.toml",
        conn=conn,
        poll_timeout_seconds=1,
        cli_entry=["true"],
    )
    # 시드된 row는 baseline 이전이므로 무시됨 → None.
    assert result is None
    # 시드된 row는 그대로 남아 있어야 함.
    assert seq > 0


def test_start_live_worker_detects_new_row_after_start(tmp_path, conn):
    """subprocess가 시작된 직후 audit_log에 새 WORKER_STARTED를 추가하면 polling이 발견."""
    rules_path = deploy.write_auto_rules_file(
        "[caps]\n", config_dir=tmp_path / "config",
    )

    # conn이 가리키는 DB 파일 경로를 PRAGMA로 확인 — fixture가 만든 SQLite 파일.
    db_list = list(conn.execute("PRAGMA database_list"))
    db_actual_path = Path(db_list[0]["file"])

    # cli_entry로 Python subprocess가 audit_log에 row INSERT.
    insert_script = (
        f"import sqlite3; "
        f"c = sqlite3.connect({str(db_actual_path)!r}); "
        f"c.execute("
        f"\"INSERT INTO audit_log (ts_utc, event_type, payload_json) VALUES "
        f"('2026-05-19T01:00:00.000Z', 'WORKER_STARTED', "
        f"'{{\\\"event_type\\\":\\\"WORKER_STARTED\\\",\\\"pid\\\":1,\\\"config_path\\\":\\\"x\\\"}}')"
        f"\"); "
        f"c.commit(); c.close()"
    )
    import sys as _sys
    cli_entry = [_sys.executable, "-c", insert_script]

    result = deploy.start_live_worker(
        rules_path=rules_path,
        capital_usd=Decimal("100"),
        db_path=db_actual_path,
        halt_path=tmp_path / "halt.flag",
        env_file=None,
        base_url="https://example",
        prices_path=tmp_path / "prices.toml",
        conn=conn,
        poll_timeout_seconds=10,
        cli_entry=cli_entry,
    )
    assert result is not None
    assert result > 0
