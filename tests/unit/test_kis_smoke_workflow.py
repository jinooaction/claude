"""Regression tests for the KIS smoke workflow's deploy isolation."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "kis-smoke.yml"


def test_kis_smoke_uses_isolated_checkout_instead_of_live_repo() -> None:
    body = WORKFLOW.read_text()

    assert "LIVE_REPO=/opt/auto-invest" in body
    assert 'SMOKE_REPO="$(sudo -u auto-invest mktemp -d "${smoke_parent}/repo.XXXXXX"' in body
    assert 'clone_url="${FALLBACK_REMOTE_URL}"' in body
    assert 'git config --global --add safe.directory "${SMOKE_REPO}"' in body
    assert 'sudo -u auto-invest git config --global --add safe.directory "${SMOKE_REPO}"' in body
    assert 'git -C "${SMOKE_REPO}" fetch --quiet origin main' in body
    assert 'git -C "${SMOKE_REPO}" checkout --quiet --detach "${TARGET_SHA}"' in body
    assert 'cd "${SMOKE_REPO}"' in body
    assert '/usr/local/bin/uv run --project "${SMOKE_REPO}" pytest' in body
    assert 'read_env_value()' in body
    assert 'source "${LIVE_REPO}/.env"' not in body

    forbidden_fragments = [
        'git reset --hard origin/main',
        'git checkout main',
        'cd "${REPO}"',
        '/usr/local/bin/uv run --project "${REPO}" pytest',
    ]
    for fragment in forbidden_fragments:
        assert fragment not in body

    assert not re.search(
        r"git\s+-C\s+\"\$\{LIVE_REPO\}\"[^\n]*\b(fetch|checkout|pull|reset)\b",
        body,
    )
