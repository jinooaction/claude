"""Broker failure diagnostics with secret masking.

The order path must preserve enough evidence to classify broker failures without
leaking account or credential material. Helpers here intentionally return plain
JSON-compatible dictionaries so audit payloads and CLI JSON can store them
without a schema migration.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import httpx

_SENSITIVE_KEYS = {
    "authorization",
    "appkey",
    "appsecret",
    "app_key",
    "app_secret",
    "kis_app_key",
    "kis_app_secret",
    "access_token",
    "refresh_token",
    "token",
}
_ACCOUNT_KEYS = {"cano", "account", "account_no", "kis_account_no"}
_ACCOUNT_PRODUCT_KEYS = {"acnt_prdt_cd"}


class KisOrderError(RuntimeError):
    """Raised when KIS order submission fails after preserving diagnostics."""

    def __init__(self, message: str, *, diagnostics: dict[str, Any]) -> None:
        super().__init__(message)
        self.diagnostics = diagnostics


def _mask_account(value: object) -> str:
    text = str(value)
    if len(text) <= 2:
        return "*" * len(text)
    return "*" * max(len(text) - 2, 0) + text[-2:]


def _mask_value(key: str, value: object) -> object:
    lowered = key.lower()
    if lowered in _ACCOUNT_PRODUCT_KEYS:
        return "**"
    if lowered in _ACCOUNT_KEYS:
        return _mask_account(value)
    if lowered in _SENSITIVE_KEYS or "secret" in lowered or "token" in lowered:
        return "***"
    return value


def sanitize_for_broker_diagnostics(value: object) -> object:
    """Return a JSON-compatible copy with known secret/account fields masked."""
    if isinstance(value, Mapping):
        return {
            str(k): sanitize_for_broker_diagnostics(_mask_value(str(k), v))
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [sanitize_for_broker_diagnostics(v) for v in value]
    if isinstance(value, tuple):
        return [sanitize_for_broker_diagnostics(v) for v in value]
    return value


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "...<truncated>"


def _sensitive_values(value: object) -> set[str]:
    values: set[str] = set()
    if isinstance(value, Mapping):
        for key, item in value.items():
            lowered = str(key).lower()
            if lowered in _ACCOUNT_KEYS | _ACCOUNT_PRODUCT_KEYS | _SENSITIVE_KEYS:
                text = str(item)
                if text:
                    values.add(text)
            values.update(_sensitive_values(item))
    elif isinstance(value, list | tuple):
        for item in value:
            values.update(_sensitive_values(item))
    return values


def _mask_text(text: str, *, sensitive_values: set[str]) -> str:
    masked = text
    for value in sorted(sensitive_values, key=len, reverse=True):
        if len(value) < 2:
            continue
        replacement = _mask_account(value) if value.isdigit() else "***"
        masked = masked.replace(value, replacement)
    return masked


def _endpoint_from_request(request: httpx.Request | None) -> str | None:
    if request is None:
        return None
    return request.url.path


def _json_field(body: object, key: str) -> object | None:
    if isinstance(body, Mapping):
        value = body.get(key)
        if value is not None:
            return value
    return None


def _request_from_response(response: httpx.Response) -> httpx.Request | None:
    try:
        return response.request
    except RuntimeError:
        return None


def diagnostics_from_response(
    response: httpx.Response,
    *,
    request_summary: Mapping[str, Any] | None = None,
    message: str = "",
    exception_type: str | None = None,
    request: httpx.Request | None = None,
    response_body_limit: int = 2048,
) -> dict[str, Any]:
    """Build masked diagnostics from a broker response, including HTTP 200 errors."""
    raw_request_summary = dict(request_summary or {})
    sensitive_values = _sensitive_values(raw_request_summary)
    request = request or _request_from_response(response)
    diagnostics: dict[str, Any] = {
        "exception_type": exception_type,
        "message": _truncate(message, 1000),
        "http_status": response.status_code,
        "method": request.method if request is not None else None,
        "endpoint": _endpoint_from_request(request),
        "kis_rt_cd": None,
        "kis_msg_cd": None,
        "kis_msg1": None,
        "response_body_preview": None,
        "response_json": None,
        "request_summary": sanitize_for_broker_diagnostics(raw_request_summary),
    }

    try:
        body_text = response.text
    except Exception:  # noqa: BLE001 - diagnostics must not mask original failure.
        body_text = ""
    diagnostics["response_body_preview"] = _truncate(
        _mask_text(body_text, sensitive_values=sensitive_values),
        response_body_limit,
    )
    try:
        response_json = response.json()
    except json.JSONDecodeError:
        response_json = None
    if response_json is not None:
        diagnostics["response_json"] = sanitize_for_broker_diagnostics(response_json)
        diagnostics["kis_rt_cd"] = _json_field(response_json, "rt_cd")
        diagnostics["kis_msg_cd"] = _json_field(response_json, "msg_cd")
        diagnostics["kis_msg1"] = _json_field(response_json, "msg1")
    return diagnostics


def diagnostics_from_exception(
    exc: BaseException,
    *,
    request_summary: Mapping[str, Any] | None = None,
    response_body_limit: int = 2048,
) -> dict[str, Any]:
    """Build masked, durable diagnostics from a broker exception."""
    raw_request_summary = dict(request_summary or {})
    diagnostics: dict[str, Any] = {
        "exception_type": type(exc).__name__,
        "message": _truncate(str(exc), 1000),
        "http_status": None,
        "method": None,
        "endpoint": None,
        "kis_rt_cd": None,
        "kis_msg_cd": None,
        "kis_msg1": None,
        "response_body_preview": None,
        "response_json": None,
        "request_summary": sanitize_for_broker_diagnostics(raw_request_summary),
    }

    if isinstance(exc, httpx.HTTPStatusError):
        response = exc.response
        request = exc.request or response.request
        diagnostics.update(
            diagnostics_from_response(
                response,
                request_summary=raw_request_summary,
                message=str(exc),
                exception_type=type(exc).__name__,
                request=request,
                response_body_limit=response_body_limit,
            )
        )

    return diagnostics
