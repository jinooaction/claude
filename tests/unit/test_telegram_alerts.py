from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx

from auto_invest.notifications.audit_tail import (
    format_alert,
    load_cursor,
    process_once,
)
from auto_invest.notifications.telegram import (
    TelegramConfig,
    TelegramNotifier,
    sanitize_for_alert,
)
from auto_invest.persistence import audit, db
from auto_invest.persistence.audit import (
    ErrorPayload,
    FillPayload,
    OrderRejectedByBrokerPayload,
    OrderSubmittedPayload,
)


def _db(tmp_path: Path) -> Path:
    db_path = tmp_path / "auto_invest.db"
    conn = db.get_connection(db_path)
    db.migrate(conn)
    conn.close()
    return db_path


def test_sanitize_for_alert_masks_nested_secrets_and_accounts() -> None:
    value = {
        "authorization": "Bearer secret-token",
        "CANO": "12345678",
        "ACNT_PRDT_CD": "01",
        "nested": {"app_secret": "abc123", "safe": "IEF"},
    }
    out = sanitize_for_alert(value)
    assert out["authorization"] == "***"
    assert out["CANO"] == "******78"
    assert out["ACNT_PRDT_CD"] == "**"
    assert out["nested"]["app_secret"] == "***"
    assert out["nested"]["safe"] == "IEF"


def test_format_broker_rejection_alert_masks_sensitive_values(tmp_path: Path) -> None:
    db_path = _db(tmp_path)
    conn = db.get_connection(db_path)
    try:
        seq = audit.append(
            conn,
            OrderRejectedByBrokerPayload(
                broker_code="KIS",
                broker_message="server rejected",
                diagnostics={
                    "http_status": 500,
                    "kis_msg_cd": "APBK001",
                    "kis_msg1": "invalid account 12345678 token secret-token",
                    "request_summary": {
                        "body": {
                            "CANO": "12345678",
                            "ACNT_PRDT_CD": "01",
                            "appkey": "secret-token",
                        }
                    },
                },
            ),
            symbol="IEF",
            correlation_id="cid-1",
        )
        row = conn.execute("SELECT * FROM audit_log WHERE seq = ?", (seq,)).fetchone()
    finally:
        conn.close()

    message = format_alert(row, source_label="test")
    assert "브로커 거부" in message
    assert "http=500" in message
    assert "msg_cd=APBK001" in message
    assert "IEF" in message
    assert "12345678" not in message
    assert "secret-token" not in message


def test_process_once_starts_at_end_without_replay(tmp_path: Path) -> None:
    db_path = _db(tmp_path)
    state = tmp_path / "state.json"
    conn = db.get_connection(db_path)
    try:
        seq = audit.append(
            conn,
            OrderSubmittedPayload(kis_order_id="K1", submitted_at_utc="2026-06-22T15:00:00Z"),
            symbol="IEF",
        )
    finally:
        conn.close()

    sent = asyncio.run(
        process_once(
            db_path=db_path,
            state_file=state,
            config=TelegramConfig(bot_token=None, chat_id=None),
            dry_run=True,
        )
    )
    assert sent == 0
    assert load_cursor(state).last_seq == seq


def test_process_once_replays_existing_and_advances_cursor(tmp_path: Path) -> None:
    db_path = _db(tmp_path)
    state = tmp_path / "state.json"
    conn = db.get_connection(db_path)
    try:
        seq = audit.append(
            conn,
            FillPayload(
                kis_fill_id="K1:1",
                qty=1,
                price_usd="94.55",
                executed_at_utc="2026-06-22T15:00:01Z",
            ),
            symbol="IEF",
        )
    finally:
        conn.close()

    class Buffer:
        def __init__(self) -> None:
            self.text = ""

        def write(self, value: str) -> None:
            self.text += value

    out = Buffer()
    sent = asyncio.run(
        process_once(
            db_path=db_path,
            state_file=state,
            config=TelegramConfig(bot_token=None, chat_id=None),
            dry_run=True,
            replay_existing=True,
            output=out,
        )
    )
    assert sent == 1
    assert "체결" in out.text
    assert "qty=1" in out.text
    assert load_cursor(state).last_seq == seq


def test_process_once_caps_stale_cursor_catchup_to_newest_rows(tmp_path: Path) -> None:
    db_path = _db(tmp_path)
    state = tmp_path / "state.json"
    conn = db.get_connection(db_path)
    try:
        for idx in range(10):
            audit.append(
                conn,
                OrderSubmittedPayload(
                    kis_order_id=f"K{idx}",
                    submitted_at_utc="2026-06-22T15:00:00Z",
                ),
                symbol="IEF",
            )
        last_seq = conn.execute("SELECT MAX(seq) AS seq FROM audit_log").fetchone()["seq"]
    finally:
        conn.close()
    state.write_text(
        json.dumps({"last_seq": 0, "updated_at_utc": "2026-06-22T15:00:00Z"}),
        encoding="utf-8",
    )

    class Buffer:
        def __init__(self) -> None:
            self.text = ""

        def write(self, value: str) -> None:
            self.text += value

    out = Buffer()
    sent = asyncio.run(
        process_once(
            db_path=db_path,
            state_file=state,
            config=TelegramConfig(bot_token=None, chat_id=None),
            dry_run=True,
            max_catchup_alerts=3,
            output=out,
        )
    )

    assert sent == 3
    assert "kis_order_id=K7" in out.text
    assert "kis_order_id=K8" in out.text
    assert "kis_order_id=K9" in out.text
    assert "kis_order_id=K0" not in out.text
    assert load_cursor(state).last_seq == last_seq


def test_process_once_suppresses_repeated_error_alerts_with_cooldown(tmp_path: Path) -> None:
    db_path = _db(tmp_path)
    state = tmp_path / "state.json"
    conn = db.get_connection(db_path)
    try:
        for _ in range(3):
            audit.append(
                conn,
                ErrorPayload(where="worker.loop", message="same failure", exc_type="RuntimeError"),
                symbol="IEF",
            )
        third_seq = conn.execute("SELECT MAX(seq) AS seq FROM audit_log").fetchone()["seq"]
    finally:
        conn.close()

    class Buffer:
        def __init__(self) -> None:
            self.text = ""

        def write(self, value: str) -> None:
            self.text += value

    out = Buffer()
    sent = asyncio.run(
        process_once(
            db_path=db_path,
            state_file=state,
            config=TelegramConfig(bot_token=None, chat_id=None),
            dry_run=True,
            replay_existing=True,
            output=out,
        )
    )
    assert sent == 1
    assert out.text.count("auto-invest 오류") == 1
    assert load_cursor(state).last_seq == third_seq

    conn = db.get_connection(db_path)
    try:
        fourth_seq = audit.append(
            conn,
            ErrorPayload(where="worker.loop", message="same failure", exc_type="RuntimeError"),
            symbol="IEF",
        )
    finally:
        conn.close()

    sent = asyncio.run(
        process_once(
            db_path=db_path,
            state_file=state,
            config=TelegramConfig(bot_token=None, chat_id=None),
            dry_run=True,
        )
    )
    assert sent == 0
    assert load_cursor(state).last_seq == fourth_seq


def test_telegram_notifier_retries_then_succeeds() -> None:
    calls: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(500, json={"ok": False})
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)

    async def run() -> None:
        async with httpx.AsyncClient(transport=transport) as client:
            notifier = TelegramNotifier(
                TelegramConfig(bot_token="token-1234", chat_id="chat-99", max_retries=1),
                client=client,
            )
            await notifier.send_message("hello")

    asyncio.run(run())
    assert len(calls) == 2
    body = json.loads(calls[-1].content)
    assert body["chat_id"] == "chat-99"
    assert body["text"] == "hello"
