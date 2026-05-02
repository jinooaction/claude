"""KIS OAuth2 token issuance + on-disk cache (FR-008).

KIS access tokens are valid for ~24 hours. We persist the token to a
small JSON file so a worker restart does not re-issue when an existing
token is still valid. Refresh kicks in when the remaining lifetime
falls below `TOKEN_REFRESH_MARGIN`.

Every fresh token value is registered with the redaction filter the
moment it is parsed so the actual token never appears in logs.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
from pydantic import BaseModel, ConfigDict

from auto_invest.logging_config import register_secret

TOKEN_REFRESH_MARGIN = timedelta(minutes=10)


class AccessToken(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    access_token: str
    token_type: str
    expires_at_utc: datetime

    def is_valid(
        self,
        now: datetime,
        margin: timedelta = TOKEN_REFRESH_MARGIN,
    ) -> bool:
        return now + margin < self.expires_at_utc


def _utcnow() -> datetime:
    return datetime.now(UTC)


def load_cached_token(cache_path: Path) -> AccessToken | None:
    """Return the cached token if present and parseable, else None."""
    if not cache_path.exists():
        return None
    try:
        return AccessToken.model_validate_json(cache_path.read_text(encoding="utf-8"))
    except Exception:
        return None


def save_token(cache_path: Path, token: AccessToken) -> None:
    """Write the token to disk; creates parent directories on demand."""
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(token.model_dump_json(), encoding="utf-8")


async def issue_token(
    client: httpx.AsyncClient,
    *,
    base_url: str,
    app_key: str,
    app_secret: str,
) -> AccessToken:
    """Issue a fresh access token via KIS `/oauth2/tokenP`."""
    response = await client.post(
        f"{base_url}/oauth2/tokenP",
        json={
            "grant_type": "client_credentials",
            "appkey": app_key,
            "appsecret": app_secret,
        },
        headers={"content-type": "application/json"},
    )
    response.raise_for_status()
    body = response.json()
    expires_in = int(body.get("expires_in", 86400))
    token = AccessToken(
        access_token=body["access_token"],
        token_type=body.get("token_type", "Bearer"),
        expires_at_utc=_utcnow() + timedelta(seconds=expires_in),
    )
    register_secret(token.access_token)
    return token


async def get_valid_token(
    client: httpx.AsyncClient,
    *,
    base_url: str,
    app_key: str,
    app_secret: str,
    cache_path: Path,
    now: datetime | None = None,
) -> AccessToken:
    """Return a valid access token, reusing the cached one when possible."""
    moment = now or _utcnow()
    cached = load_cached_token(cache_path)
    if cached and cached.is_valid(moment):
        register_secret(cached.access_token)
        return cached
    fresh = await issue_token(
        client,
        base_url=base_url,
        app_key=app_key,
        app_secret=app_secret,
    )
    save_token(cache_path, fresh)
    return fresh
