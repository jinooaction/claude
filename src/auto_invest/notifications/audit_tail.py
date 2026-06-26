"""Read audit_log rows and convert order events to Telegram alerts."""

from __future__ import annotations

import asyncio
import hashlib
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
DEFAULT_MAX_CATCHUP_ALERTS = 25
DEFAULT_ERROR_COOLDOWN_SECONDS = 3600.0


@dataclass(frozen=True)
class AlertCursor:
    last_seq: int
    updated_at_utc: str
    error_alerts: dict[str, str]


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
        error_alerts=dict(raw.get("error_alerts") or {}),
    )


def save_cursor(path: Path, cursor: AlertCursor | int) -> None:
    if isinstance(cursor, int):
        cursor = AlertCursor(last_seq=cursor, updated_at_utc=_now_iso(), error_alerts={})
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(
            {
                "last_seq": int(cursor.last_seq),
                "updated_at_utc": _now_iso(),
                "error_alerts": cursor.error_alerts,
            },
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


def count_alert_rows(
    conn: sqlite3.Connection,
    *,
    after_seq: int,
    include_paper: bool = False,
) -> int:
    events = _event_types(include_paper=include_paper)
    placeholders = ",".join("?" for _ in events)
    row = conn.execute(
        f"""
        SELECT COUNT(*) AS count
        FROM audit_log
        WHERE seq > ? AND event_type IN ({placeholders})
        """,
        (after_seq, *events),
    ).fetchone()
    return int(row["count"])


def bounded_catchup_after_seq(
    conn: sqlite3.Connection,
    *,
    after_seq: int,
    include_paper: bool = False,
    max_catchup_alerts: int = DEFAULT_MAX_CATCHUP_ALERTS,
) -> int:
    """Return an after_seq that caps stale-cursor catch-up to newest N alert rows."""
    if max_catchup_alerts < 0:
        return after_seq
    pending = count_alert_rows(conn, after_seq=after_seq, include_paper=include_paper)
    if pending <= max_catchup_alerts:
        return after_seq
    if max_catchup_alerts == 0:
        return max_audit_seq(conn)

    events = _event_types(include_paper=include_paper)
    placeholders = ",".join("?" for _ in events)
    row = conn.execute(
        f"""
        SELECT seq
        FROM audit_log
        WHERE seq > ? AND event_type IN ({placeholders})
        ORDER BY seq DESC
        LIMIT 1 OFFSET ?
        """,
        (after_seq, *events, max_catchup_alerts - 1),
    ).fetchone()
    return max(int(row["seq"]) - 1, after_seq) if row is not None else after_seq


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


def _join_parts(*parts: str | None) -> str:
    return " ".join(part for part in parts if part)


def _nested_dict(value: object, key: str) -> dict:
    if not isinstance(value, dict):
        return {}
    nested = value.get(key)
    return nested if isinstance(nested, dict) else {}


def _kis_request_summary(diagnostics: dict) -> str:
    request = _nested_dict(diagnostics, "request_summary")
    body = _nested_dict(request, "body")
    if not body:
        return ""
    return _join_parts(
        _line("pdno", body.get("PDNO")),
        _line("qty", body.get("ORD_QTY")),
        _line("limit", body.get("OVRS_ORD_UNPR")),
        _line("exchange", body.get("OVRS_EXCG_CD")),
        _line("side_code", body.get("SLL_BUY_DVSN_CD")),
    )


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
    status = {
        "ORDER_INTENT": "라우터가 주문 제출을 준비했습니다.",
        "ORDER_SUBMITTED": (
            "브로커가 주문을 접수했습니다. 체결은 FILL 이벤트로 별도 확인합니다."
        ),
        "ORDER_REJECTED_BY_GATE": (
            "내부 안전 게이트가 주문을 막았습니다. 브로커에는 제출되지 않았습니다."
        ),
        "ORDER_REJECTED_BY_BROKER": "브로커가 주문을 거부했습니다. 접수/체결 0건으로 봅니다.",
        "FILL": "체결 기록이 들어왔습니다.",
        "CANCEL": "주문 취소 이벤트가 들어왔습니다.",
        "CIRCUIT_BREAKER_TRIPPED": "손실 브레이커가 동작했습니다.",
        "HALT_SET": "거래 중지 플래그가 설정되었습니다.",
        "ERROR": "운영 오류가 기록되었습니다.",
        "ORDER_PAPER_FILLED": "페이퍼 주문이 시뮬레이션 체결되었습니다.",
    }.get(event, "감사 로그 이벤트가 기록되었습니다.")
    lines = [
        f"[{source_label}] {title}",
        f"상태: {status}",
        f"이벤트: {event} seq={row['seq']} ts_utc={row['ts_utc']}",
    ]
    context = [
        _line("symbol", row["symbol"]),
        _line("rule", row["rule_id"]),
        _line("correlation", row["correlation_id"]),
    ]
    context_line = _join_parts(*context)
    if context_line:
        lines.append(f"대상: {context_line}")

    if event == "ORDER_INTENT":
        lines.append(
            "주문: "
            + _join_parts(
                _line("side", payload.get("side")),
                _line("qty", payload.get("qty")),
                _line("type", payload.get("order_type")),
                _line("limit", payload.get("limit_price_usd")),
            )
        )
    elif event == "ORDER_SUBMITTED":
        lines.append(
            "접수: "
            + _join_parts(
                _line("kis_order_id", payload.get("kis_order_id")),
                _line("submitted_at", payload.get("submitted_at_utc")),
            )
        )
    elif event == "ORDER_REJECTED_BY_GATE":
        lines.append(
            "거부: "
            + _join_parts(
                _line("gate", payload.get("gate")),
                _line("reason", payload.get("reason")),
            )
        )
    elif event == "ORDER_REJECTED_BY_BROKER":
        diagnostics = payload.get("diagnostics") or {}
        diag = diagnostics if isinstance(diagnostics, dict) else {}
        lines.append(
            "진단: "
            + _join_parts(
                _line("broker", payload.get("broker_code")),
                _line("message", payload.get("broker_message")),
                _line("http", diag.get("http_status")),
                _line("msg_cd", diag.get("kis_msg_cd")),
                _line("msg", diag.get("kis_msg1")),
            )
        )
        request_summary = _kis_request_summary(diag)
        if request_summary:
            lines.append(f"요청: {request_summary}")
        lines.append("판단: 주문은 브로커에서 거부되어 접수·체결되지 않았습니다.")
    elif event in {"FILL", "ORDER_PAPER_FILLED"}:
        lines.append(
            "체결: "
            + _join_parts(
                _line("qty", payload.get("qty")),
                _line(
                    "price",
                    payload.get("price_usd") or payload.get("fill_price_usd"),
                ),
                _line("executed_at", payload.get("executed_at_utc")),
            )
        )
    elif event == "CANCEL":
        lines.append(
            "취소: " + (_line("reason", payload.get("reason")) or "reason=unknown")
        )
    elif event == "CIRCUIT_BREAKER_TRIPPED":
        lines.append(
            "브레이커: "
            + (_line("reason", payload.get("reason")) or str(payload))
        )
    elif event == "HALT_SET":
        lines.append(
            "중지: " + (_line("reason", payload.get("reason")) or "reason=unknown")
        )
    elif event == "ERROR":
        lines.append(
            "오류: "
            + _join_parts(
                _line("where", payload.get("where")),
                _line("type", payload.get("exc_type")),
                _line("message", payload.get("message")),
            )
        )
    else:
        lines.append(json.dumps(payload, ensure_ascii=False, sort_keys=True))

    text = "\n".join(line for line in lines if line)
    return truncate_message(text)


def _parse_iso(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def _error_fingerprint(row: sqlite3.Row) -> str:
    payload = _payload(row)
    fingerprint = {
        "event_type": row["event_type"],
        "where": payload.get("where"),
        "exc_type": payload.get("exc_type"),
        "message": payload.get("message"),
        "symbol": row["symbol"],
        "rule_id": row["rule_id"],
    }
    encoded = json.dumps(fingerprint, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _should_send_error(
    cursor: AlertCursor,
    row: sqlite3.Row,
    *,
    error_cooldown_seconds: float,
    now: datetime,
) -> bool:
    if row["event_type"] != "ERROR" or error_cooldown_seconds <= 0:
        return True
    last_sent = cursor.error_alerts.get(_error_fingerprint(row))
    if last_sent is None:
        return True
    parsed = _parse_iso(last_sent)
    if parsed is None:
        return True
    return (now - parsed).total_seconds() >= error_cooldown_seconds


def _advance_cursor(
    cursor: AlertCursor,
    row: sqlite3.Row,
    *,
    sent: bool,
    now_iso: str,
) -> AlertCursor:
    error_alerts = dict(cursor.error_alerts)
    if sent and row["event_type"] == "ERROR":
        error_alerts[_error_fingerprint(row)] = now_iso
    return AlertCursor(last_seq=int(row["seq"]), updated_at_utc=now_iso, error_alerts=error_alerts)


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
    max_catchup_alerts: int = DEFAULT_MAX_CATCHUP_ALERTS,
    error_cooldown_seconds: float = DEFAULT_ERROR_COOLDOWN_SECONDS,
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
        cursor = cursor or AlertCursor(last_seq=0, updated_at_utc="", error_alerts={})
        last_seq = cursor.last_seq
        if not replay_existing:
            last_seq = bounded_catchup_after_seq(
                conn,
                after_seq=last_seq,
                include_paper=include_paper,
                max_catchup_alerts=max_catchup_alerts,
            )
            if last_seq != cursor.last_seq:
                cursor = AlertCursor(
                    last_seq=last_seq,
                    updated_at_utc=_now_iso(),
                    error_alerts=cursor.error_alerts,
                )
                save_cursor(state_file, cursor)
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
        now = datetime.now(UTC)
        now_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        if not _should_send_error(
            cursor,
            row,
            error_cooldown_seconds=error_cooldown_seconds,
            now=now,
        ):
            cursor = _advance_cursor(cursor, row, sent=False, now_iso=now_iso)
            save_cursor(state_file, cursor)
            continue
        message = format_alert(row, source_label=config.source_label)
        if dry_run:
            if output is not None:
                output.write(message + "\n---\n")
        else:
            await sender.send_message(message)
        cursor = _advance_cursor(cursor, row, sent=True, now_iso=now_iso)
        save_cursor(state_file, cursor)
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
    max_catchup_alerts: int = DEFAULT_MAX_CATCHUP_ALERTS,
    error_cooldown_seconds: float = DEFAULT_ERROR_COOLDOWN_SECONDS,
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
                max_catchup_alerts=max_catchup_alerts,
                error_cooldown_seconds=error_cooldown_seconds,
                output=output,
            )
        finally:
            first = False
        await asyncio.sleep(poll_interval_seconds)
