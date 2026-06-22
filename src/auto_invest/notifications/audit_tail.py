"""Read audit_log rows and convert order events to Telegram alerts."""

from __future__ import annotations

import asyncio
import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TextIO

from auto_invest.notifications.telegram import (
    TelegramConfig,
    TelegramNotifier,
    sanitize_for_alert,
    truncate_message,
)
from auto_invest.persistence import db

DEFAULT_EVENT_TYPES = (
    "ORDER_INTENT",
    "ORDER_SUBMITTED",
    "ORDER_REJECTED_BY_GATE",
    "ORDER_REJECTED_BY_BROKER",
    "FILL",
    "CANCEL",
    "CIRCUIT_BREAKER_TRIPPED",
    "HALT_SET",
    "ERROR",
)
PAPER_EVENT_TYPES = ("ORDER_PAPER_FILLED",)


@dataclass(frozen=True)
class AlertCursor:
    last_seq: int
    updated_at_utc: str


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_cursor(path: Path) -> AlertCursor | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    return AlertCursor(
        last_seq=int(raw.get("last_seq", 0)),
        updated_at_utc=str(raw.get("updated_at_utc", "")),
    )


def save_cursor(path: Path, last_seq: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(
            {"last_seq": int(last_seq), "updated_at_utc": _now_iso()},
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    tmp.replace(path)


def max_audit_seq(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COALESCE(MAX(seq), 0) AS seq FROM audit_log").fetchone()
    return int(row["seq"])


def _event_types(*, include_paper: bool) -> tuple[str, ...]:
    if include_paper:
        return DEFAULT_EVENT_TYPES + PAPER_EVENT_TYPES
    return DEFAULT_EVENT_TYPES


def fetch_alert_rows(
    conn: sqlite3.Connection,
    *,
    after_seq: int,
    include_paper: bool = False,
    limit: int = 100,
) -> list[sqlite3.Row]:
    events = _event_types(include_paper=include_paper)
    placeholders = ",".join("?" for _ in events)
    return list(
        conn.execute(
            f"""
            SELECT seq, ts_utc, event_type, rule_id, symbol, payload_json, correlation_id
            FROM audit_log
            WHERE seq > ? AND event_type IN ({placeholders})
            ORDER BY seq
            LIMIT ?
            """,
            (after_seq, *events, limit),
        )
    )


def _payload(row: sqlite3.Row) -> dict:
    try:
        raw = json.loads(row["payload_json"])
    except json.JSONDecodeError:
        return {"unparseable_payload": row["payload_json"]}
    sanitized = sanitize_for_alert(raw)
    return sanitized if isinstance(sanitized, dict) else {"payload": sanitized}


def _line(label: str, value: object | None) -> str | None:
    if value in (None, ""):
        return None
    return f"{label}={value}"


def format_alert(row: sqlite3.Row, *, source_label: str = "auto-invest") -> str:
    payload = _payload(row)
    event = row["event_type"]
    title = {
        "ORDER_INTENT": "주문 의도",
        "ORDER_SUBMITTED": "주문 접수",
        "ORDER_REJECTED_BY_GATE": "게이트 거부",
        "ORDER_REJECTED_BY_BROKER": "브로커 거부",
        "FILL": "체결",
        "CANCEL": "취소",
        "CIRCUIT_BREAKER_TRIPPED": "손실 브레이커",
        "HALT_SET": "중지 설정",
        "ERROR": "오류",
        "ORDER_PAPER_FILLED": "페이퍼 체결",
    }.get(event, event)
    lines = [
        f"{source_label} {title}",
        f"event={event} seq={row['seq']} ts={row['ts_utc']}",
    ]
    context = [
        _line("symbol", row["symbol"]),
        _line("rule", row["rule_id"]),
        _line("correlation", row["correlation_id"]),
    ]
    lines.extend(item for item in context if item)

    if event == "ORDER_INTENT":
        lines.append(
            " ".join(
                item
                for item in (
                    _line("side", payload.get("side")),
                    _line("qty", payload.get("qty")),
                    _line("type", payload.get("order_type")),
                    _line("limit", payload.get("limit_price_usd")),
                )
                if item
            )
        )
    elif event == "ORDER_SUBMITTED":
        lines.append(
            " ".join(
                item
                for item in (
                    _line("kis_order_id", payload.get("kis_order_id")),
                    _line("submitted_at", payload.get("submitted_at_utc")),
                )
                if item
            )
        )
    elif event == "ORDER_REJECTED_BY_GATE":
        lines.append(
            " ".join(
                item
                for item in (
                    _line("gate", payload.get("gate")),
                    _line("reason", payload.get("reason")),
                )
                if item
            )
        )
    elif event == "ORDER_REJECTED_BY_BROKER":
        diagnostics = payload.get("diagnostics") or {}
        diag = diagnostics if isinstance(diagnostics, dict) else {}
        lines.append(
            " ".join(
                item
                for item in (
                    _line("broker", payload.get("broker_code")),
                    _line("message", payload.get("broker_message")),
                    _line("http", diag.get("http_status")),
                    _line("msg_cd", diag.get("kis_msg_cd")),
                    _line("msg", diag.get("kis_msg1")),
                )
                if item
            )
        )
    elif event in {"FILL", "ORDER_PAPER_FILLED"}:
        lines.append(
            " ".join(
                item
                for item in (
                    _line("qty", payload.get("qty")),
                    _line("price", payload.get("price_usd") or payload.get("fill_price_usd")),
                    _line("executed_at", payload.get("executed_at_utc")),
                )
                if item
            )
        )
    elif event == "CANCEL":
        lines.append(_line("reason", payload.get("reason")) or "")
    elif event == "CIRCUIT_BREAKER_TRIPPED":
        lines.append(_line("reason", payload.get("reason")) or str(payload))
    elif event == "HALT_SET":
        lines.append(_line("reason", payload.get("reason")) or "")
    elif event == "ERROR":
        lines.append(
            " ".join(
                item
                for item in (
                    _line("where", payload.get("where")),
                    _line("type", payload.get("exc_type")),
                    _line("message", payload.get("message")),
                )
                if item
            )
        )
    else:
        lines.append(json.dumps(payload, ensure_ascii=False, sort_keys=True))

    text = "\n".join(line for line in lines if line)
    return truncate_message(text)


async def process_once(
    *,
    db_path: Path,
    state_file: Path,
    config: TelegramConfig,
    notifier: TelegramNotifier | None = None,
    dry_run: bool = False,
    replay_existing: bool = False,
    include_paper: bool = False,
    limit: int = 100,
    output: TextIO | None = None,
) -> int:
    if not db_path.exists():
        raise FileNotFoundError(f"database not found: {db_path}")

    conn = db.get_connection(db_path)
    try:
        cursor = load_cursor(state_file)
        if cursor is None and not replay_existing:
            last = max_audit_seq(conn)
            save_cursor(state_file, last)
            return 0
        last_seq = cursor.last_seq if cursor is not None else 0
        rows = fetch_alert_rows(
            conn,
            after_seq=last_seq,
            include_paper=include_paper,
            limit=limit,
        )
    finally:
        conn.close()

    sent = 0
    sender = notifier or TelegramNotifier(config)
    for row in rows:
        message = format_alert(row, source_label=config.source_label)
        if dry_run:
            if output is not None:
                output.write(message + "\n---\n")
        else:
            await sender.send_message(message)
        save_cursor(state_file, int(row["seq"]))
        sent += 1
    return sent


async def follow(
    *,
    db_path: Path,
    state_file: Path,
    config: TelegramConfig,
    dry_run: bool = False,
    replay_existing: bool = False,
    include_paper: bool = False,
    poll_interval_seconds: float = 5.0,
    output: TextIO | None = None,
) -> None:
    first = True
    while True:
        try:
            await process_once(
                db_path=db_path,
                state_file=state_file,
                config=config,
                dry_run=dry_run,
                replay_existing=replay_existing if first else False,
                include_paper=include_paper,
                output=output,
            )
        finally:
            first = False
        await asyncio.sleep(poll_interval_seconds)
