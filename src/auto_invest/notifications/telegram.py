"""Telegram notification transport with secret masking.

This module is intentionally small and best-effort. It never places orders and
callers must keep it outside the trading decision path.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import httpx
from dotenv import dotenv_values

from auto_invest.logging_config import register_secret

TELEGRAM_MAX_TEXT = 4096
DEFAULT_MESSAGE_LIMIT = 3800

_SENSITIVE_KEYS = {
    "authorization",
    "appkey",
    "appsecret",
    "app_key",
    "app_secret",
    "kis_app_key",
    "kis_app_secret",
    "telegram_bot_token",
    "bot_token",
    "access_token",
    "refresh_token",
    "token",
}
_ACCOUNT_KEYS = {"cano", "account", "account_no", "kis_account_no", "chat_id"}
_ACCOUNT_PRODUCT_KEYS = {"acnt_prdt_cd"}


class TelegramConfigError(ValueError):
    """Raised when Telegram notification settings are required but invalid."""


@dataclass(frozen=True)
class TelegramConfig:
    bot_token: str | None
    chat_id: str | None
    enabled: bool = True
    source_label: str = "auto-invest"
    timeout_seconds: float = 8.0
    max_retries: int = 2

    @property
    def can_send(self) -> bool:
        return self.enabled and bool(self.bot_token and self.chat_id)


def _merged_env(env_file: Path | None) -> dict[str, str]:
    merged: dict[str, str] = {}
    if env_file is not None and env_file.exists():
        for key, value in dotenv_values(env_file).items():
            if value is not None:
                merged[key] = value
    for key, value in os.environ.items():
        merged[key] = value
    return merged


def load_telegram_config(
    env_file: Path | None = None,
    *,
    require: bool = False,
) -> TelegramConfig:
    env = _merged_env(env_file)
    enabled = env.get("TELEGRAM_ENABLED", "true").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }
    token = env.get("TELEGRAM_BOT_TOKEN", "").strip() or None
    chat_id = env.get("TELEGRAM_CHAT_ID", "").strip() or None
    source = env.get("TELEGRAM_SOURCE_LABEL", "auto-invest").strip() or "auto-invest"
    timeout = float(env.get("TELEGRAM_TIMEOUT_SECONDS", "8"))
    retries = max(0, int(env.get("TELEGRAM_MAX_RETRIES", "2")))

    if token:
        register_secret(token)
    if chat_id:
        register_secret(chat_id)

    cfg = TelegramConfig(
        bot_token=token,
        chat_id=chat_id,
        enabled=enabled,
        source_label=source,
        timeout_seconds=timeout,
        max_retries=retries,
    )
    if require and not cfg.can_send:
        raise TelegramConfigError(
            "Telegram alerts require TELEGRAM_ENABLED=true, TELEGRAM_BOT_TOKEN, "
            "and TELEGRAM_CHAT_ID"
        )
    return cfg


def _mask_account(value: object) -> str:
    text = str(value)
    if len(text) <= 2:
        return "*" * len(text)
    return "*" * (len(text) - 2) + text[-2:]


def _mask_value(key: str, value: object) -> object:
    lowered = key.lower()
    if lowered in _ACCOUNT_PRODUCT_KEYS:
        return "**"
    if lowered in _ACCOUNT_KEYS:
        return _mask_account(value)
    if lowered in _SENSITIVE_KEYS or "secret" in lowered or "token" in lowered:
        return "***"
    return value


def _sensitive_values(value: object) -> set[str]:
    values: set[str] = set()
    if isinstance(value, Mapping):
        for key, item in value.items():
            lowered = str(key).lower()
            if (
                lowered in _ACCOUNT_KEYS
                or lowered in _SENSITIVE_KEYS
                or "secret" in lowered
                or "token" in lowered
            ):
                text = str(item)
                if text:
                    values.add(text)
            values.update(_sensitive_values(item))
    elif isinstance(value, list | tuple):
        for item in value:
            values.update(_sensitive_values(item))
    return values


def _mask_text(text: str, sensitive_values: set[str]) -> str:
    masked = text
    for value in sorted(sensitive_values, key=len, reverse=True):
        if len(value) < 2:
            continue
        replacement = _mask_account(value) if value.isdigit() else "***"
        masked = masked.replace(value, replacement)
    return masked


def _sanitize_for_alert(value: object, sensitive_values: set[str]) -> object:
    """Return a JSON-compatible copy with known secret/account fields masked."""
    if isinstance(value, Mapping):
        return {
            str(k): _sanitize_for_alert(_mask_value(str(k), v), sensitive_values)
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [_sanitize_for_alert(item, sensitive_values) for item in value]
    if isinstance(value, tuple):
        return [_sanitize_for_alert(item, sensitive_values) for item in value]
    if isinstance(value, str):
        return _mask_text(value, sensitive_values)
    return value


def sanitize_for_alert(value: object) -> object:
    """Return a JSON-compatible copy with known secret/account fields masked."""
    return _sanitize_for_alert(value, _sensitive_values(value))


def truncate_message(text: str, *, limit: int = DEFAULT_MESSAGE_LIMIT) -> str:
    if limit >= TELEGRAM_MAX_TEXT:
        limit = TELEGRAM_MAX_TEXT - 32
    if len(text) <= limit:
        return text
    return text[:limit] + "\n...<truncated>"


class TelegramNotifier:
    """Bounded Telegram sendMessage client."""

    def __init__(self, config: TelegramConfig, *, client: httpx.AsyncClient | None = None) -> None:
        self.config = config
        self._client = client

    async def send_message(self, text: str) -> None:
        if not self.config.can_send:
            raise TelegramConfigError("Telegram alerts are not configured")
        assert self.config.bot_token is not None
        assert self.config.chat_id is not None

        payload = {
            "chat_id": self.config.chat_id,
            "text": truncate_message(text),
            "disable_web_page_preview": True,
        }
        url = f"https://api.telegram.org/bot{self.config.bot_token}/sendMessage"
        attempts = self.config.max_retries + 1
        last_exc: Exception | None = None

        close_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=self.config.timeout_seconds)
        try:
            for attempt in range(attempts):
                try:
                    response = await client.post(url, json=payload)
                    response.raise_for_status()
                    data = response.json()
                    if data.get("ok") is not True:
                        raise TelegramConfigError("Telegram sendMessage returned ok=false")
                    return
                except Exception as exc:  # noqa: BLE001 - caller decides whether to log/continue.
                    last_exc = exc
                    if attempt >= attempts - 1:
                        break
                    await asyncio.sleep(min(2**attempt, 5))
        finally:
            if close_client:
                await client.aclose()
        if last_exc is not None:
            raise last_exc
