#!/usr/bin/env python3
"""Redact public sidecar output before committing it to public branches."""

from __future__ import annotations

import json
import re
import sys
from collections.abc import Iterator
from pathlib import Path

TABLE_KEYS = (
    "account",
    "account_no",
    "capital",
    "capital_usd",
    "cash_usd",
    "host",
    "kis_order_id",
    "nav",
    "nav_usd",
    "order_id",
    "server",
    "total_value_usd",
)
SENSITIVE_JSON_KEYS = {
    "account",
    "accountno",
    "accountnumber",
    "account_no",
    "acntprdcd",
    "acnt_prdt_cd",
    "accesstoken",
    "access_token",
    "appkey",
    "app_key",
    "appsecret",
    "app_secret",
    "brokeraccount",
    "capital",
    "capitalusd",
    "capital_usd",
    "cano",
    "cash",
    "cashusd",
    "cash_usd",
    "host",
    "kisaccountno",
    "kis_account_no",
    "kisappid",
    "kisappkey",
    "kisappsecret",
    "kis_order_id",
    "kisorderid",
    "nav",
    "navusd",
    "nav_usd",
    "order_id",
    "orderid",
    "orderno",
    "server",
    "targetcapitalusd",
    "target_capital_usd",
    "token",
    "totalvalueusd",
    "total_value_usd",
}

PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(
            rf"(?im)^(\|\s*(?:{'|'.join(TABLE_KEYS)})\s*\|\s*)[^|\n]+(\|?)"
        ),
        r"\1[REDACTED]\2",
    ),
    (
        re.compile(
            r"(?i)(['\"]?\b(?:KIS_ACCOUNT_NO|ACCOUNT_NO|CANO|ACNT_PRDT_CD|"
            r"KIS_APP_KEY|KIS_APP_SECRET|APPSECRET|APPKEY|APP_KEY|APP_SECRET|"
            r"ACCESS_TOKEN|ACCESS-TOKEN|TOKEN|access_token|app_key|app_secret)"
            r"\b['\"]?\s*[:=]\s*)['\"]?[^,'\"\s)}\]]+['\"]?"
        ),
        r"\1[REDACTED]",
    ),
    (
        re.compile(
            r"(?i)\b(KIS_ACCOUNT_NO|ACCOUNT_NO|CANO|ACNT_PRDT_CD|"
            r"KIS_APP_KEY|KIS_APP_SECRET|APPSECRET|APPKEY|ACCESS_TOKEN|TOKEN)"
            r"\s*[:=]\s*['\"]?[^'\"\s]+"
        ),
        r"\1=[REDACTED]",
    ),
    (
        re.compile(r"(?i)\b(?:Bearer\s+)?[A-Za-z0-9_-]{24,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\b"),
        "[REDACTED_TOKEN]",
    ),
    (
        re.compile(r"\b\d{8,12}-?\d{2}\b"),
        "[REDACTED_ACCOUNT]",
    ),
    (
        re.compile(r"(?i)\b(?:kis_)?order(?:_id)?\s*[:=]\s*['\"]?[A-Za-z0-9_-]{4,}"),
        "order_id=[REDACTED_ORDER]",
    ),
    (
        re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
        "[REDACTED_HOST]",
    ),
)


def redact(text: str) -> str:
    result = text
    for pattern, replacement in PATTERNS:
        result = pattern.sub(replacement, result)
    return result


def _normalise_key(key: str) -> str:
    return re.sub(r"[^a-z0-9]", "", key.lower())


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    normalised = _normalise_key(key)
    return lowered in SENSITIVE_JSON_KEYS or normalised in SENSITIVE_JSON_KEYS


def _redact_json_value(value: object) -> object:
    if isinstance(value, dict):
        redacted: dict[str, object] = {}
        for key, item in value.items():
            redacted[key] = "[REDACTED]" if _is_sensitive_key(key) else _redact_json_value(item)
        return redacted
    if isinstance(value, list):
        return [_redact_json_value(item) for item in value]
    if isinstance(value, str):
        return redact(value)
    return value


def _iter_files(path: Path) -> Iterator[Path]:
    if path.is_dir():
        for child in path.rglob("*"):
            if ".git" in child.parts:
                continue
            if child.is_file():
                yield child
    elif path.is_file():
        yield path


def _redact_path(path: Path) -> None:
    for file_path in _iter_files(path):
        try:
            raw = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if file_path.suffix == ".json":
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                file_path.write_text(redact(raw), encoding="utf-8")
            else:
                file_path.write_text(
                    json.dumps(
                        _redact_json_value(data),
                        ensure_ascii=False,
                        indent=2,
                        sort_keys=True,
                    )
                    + "\n",
                    encoding="utf-8",
                )
        elif file_path.suffix == ".jsonl":
            redacted_lines: list[str] = []
            for line_number, line in enumerate(raw.splitlines(), start=1):
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(
                        f"invalid JSONL before redaction: {file_path}:{line_number}: {exc}"
                    ) from exc
                redacted_lines.append(
                    json.dumps(
                        _redact_json_value(data),
                        ensure_ascii=False,
                        separators=(",", ":"),
                        sort_keys=True,
                    )
                )
            file_path.write_text(
                "" if not redacted_lines else "\n".join(redacted_lines) + "\n",
                encoding="utf-8",
            )
        else:
            file_path.write_text(redact(raw), encoding="utf-8")


def main(argv: list[str]) -> int:
    if argv:
        for raw in argv:
            _redact_path(Path(raw))
    else:
        sys.stdout.write(redact(sys.stdin.read()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
