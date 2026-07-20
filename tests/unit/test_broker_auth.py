"""Tests for broker OAuth token cache hardening."""

from __future__ import annotations

import stat
from datetime import UTC, datetime

import pytest

from auto_invest.broker.auth import AccessToken, load_cached_token, save_token

EXPIRES_AT = datetime(2026, 7, 21, 12, 0, tzinfo=UTC)


def _token() -> AccessToken:
    return AccessToken(
        access_token="secret-token",
        token_type="Bearer",
        expires_at_utc=EXPIRES_AT,
    )


def test_save_token_uses_private_parent_and_file_mode(tmp_path):
    cache = tmp_path / "cache" / "kis-token.json"

    save_token(cache, _token())

    parent_mode = stat.S_IMODE(cache.parent.stat().st_mode)
    file_mode = stat.S_IMODE(cache.stat().st_mode)
    assert parent_mode == 0o700
    assert file_mode == 0o600
    assert load_cached_token(cache) == _token()


def test_save_token_refuses_to_overwrite_symlink(tmp_path):
    target = tmp_path / "target.json"
    link = tmp_path / "token.json"
    link.symlink_to(target)

    with pytest.raises(OSError, match="symlink token cache"):
        save_token(link, _token())

    assert not target.exists()


def test_load_cached_token_ignores_symlink(tmp_path):
    target = tmp_path / "target.json"
    save_token(target, _token())
    link = tmp_path / "token-link.json"
    link.symlink_to(target)

    assert load_cached_token(link) is None
