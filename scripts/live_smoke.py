#!/usr/bin/env python3
"""Interactive runner for the live KIS smoke test (T064).

Prompts for the three KIS credentials with hidden input (no echo to
the terminal), passes them to the test subprocess via environment
variables only — never to disk, never to shell history — and runs
ONLY the read-only live smoke test in tests/integration/test_live_broker.py.

Usage:
    uv run python scripts/live_smoke.py
"""

from __future__ import annotations

import getpass
import os
import re
import subprocess
import sys

HEADER = """
================================================================
  KIS Live Smoke Test
================================================================

What this does:
  1. Issues an access token via KIS /oauth2/tokenP
     (counts against your daily token-issuance quota)
  2. Fetches the current AAPL quote (read-only)
  3. NEVER places any order

How your credentials are handled:
  - input is hidden (no echo on screen)
  - passed only as env vars to the test subprocess
  - never written to disk, never in shell history
  - leave RAM when this script exits
"""

CREDENTIAL_HINTS: dict[str, str] = {
    "KIS_APP_KEY": (
        "App Key — issued at KIS Developers portal.\n"
        "  -> https://apiportal.koreainvestment.com (마이페이지 → 앱 관리)\n"
        "  format: ~36-character alphanumeric (often starts with 'PS')"
    ),
    "KIS_APP_SECRET": (
        "App Secret — paired with the app key (issued together).\n"
        "  format: long (~180 chars) base64-like string\n"
        "  IMPORTANT: shown only ONCE at issuance. If lost, reissue at\n"
        "             the same KIS Developers page (마이페이지 → 앱 관리)"
    ),
    "KIS_ACCOUNT_NO": (
        "KIS account number with overseas-stock trading enabled.\n"
        "  found at KIS HTS / mobile app → 내 계좌 → 계좌번호\n"
        "  format: 10 digits (CANO 8 + ACNT_PRDT_CD 2)\n"
        "  enter without the dash, e.g. '1234567801' for 12345678-01"
    ),
}


def _prompt_secret(name: str) -> str:
    print(f"\n[ {name} ]")
    print(CREDENTIAL_HINTS[name])
    while True:
        value = getpass.getpass(f"  {name} (input hidden): ").strip()
        if not value:
            print("  ! empty value — try again")
            continue
        return value


def _validate_account(value: str) -> bool:
    return bool(re.fullmatch(r"\d{10,}", value))


def main() -> int:
    print(HEADER)
    confirm = input("Continue? [y/N]: ").strip().lower()
    if confirm != "y":
        print("Aborted.")
        return 1

    app_key = _prompt_secret("KIS_APP_KEY")
    app_secret = _prompt_secret("KIS_APP_SECRET")
    account_no = _prompt_secret("KIS_ACCOUNT_NO")

    if not _validate_account(account_no):
        print(
            f"\n! Account number must be at least 10 digits "
            f"(received {len(account_no)} chars). Aborting."
        )
        return 2

    env = {
        **os.environ,
        "KIS_APP_KEY": app_key,
        "KIS_APP_SECRET": app_secret,
        "KIS_ACCOUNT_NO": account_no,
        "KIS_LIVE_TEST": "1",
    }

    print("\nRunning live smoke test...\n")
    result = subprocess.run(
        [
            "uv",
            "run",
            "pytest",
            "tests/integration/test_live_broker.py",
            "-v",
            "-s",
        ],
        env=env,
    )

    if result.returncode == 0:
        print("\n[OK] Live smoke test passed.")
        print("Your KIS adapter is wired correctly against the real broker.")
    else:
        print(f"\n[FAIL] Live smoke test exited with code {result.returncode}.")
        print("Common causes:")
        print("  - typo in app key / secret / account number")
        print("  - account does not have overseas-stock trading enabled")
        print("  - KIS account is not yet provisioned for OpenAPI access")
        print("  - daily token-issuance quota exceeded (wait ~1 day, retry)")
        print("  - market data subscription not active for the requested feed")
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
