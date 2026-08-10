"""Regression tests for the KIS smoke workflow's deploy isolation."""

import importlib.util
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "kis-smoke.yml"
HELPER = ROOT / "deploy" / "kis-smoke-on-instance.sh"
LIVE_BROKER = ROOT / "tests" / "integration" / "test_live_broker.py"


def test_kis_smoke_helper_uses_isolated_checkout_instead_of_live_repo() -> None:
    body = HELPER.read_text()

    assert 'LIVE_REPO="${LIVE_REPO:-/opt/auto-invest}"' in body
    assert 'SMOKE_REPO="$(sudo -u auto-invest mktemp -d "${smoke_parent}/repo.XXXXXX"' in body
    assert 'clone_url="${FALLBACK_REMOTE_URL}"' in body
    assert 'git config --global --add safe.directory "${SMOKE_REPO}"' in body
    assert 'sudo -u auto-invest git config --global --add safe.directory "${SMOKE_REPO}"' in body
    assert 'git -C "${SMOKE_REPO}" fetch --quiet origin main' in body
    assert 'merge-base --is-ancestor "${TARGET_SHA}" origin/main' in body
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


def test_kis_smoke_workflow_uses_fixed_gateway_command_not_remote_bash() -> None:
    body = WORKFLOW.read_text()

    assert '"kis-smoke ${GITHUB_SHA}"' in body
    assert "bash -s" not in body
    assert "REMOTE_SCRIPT" not in body


def test_kis_smoke_classifies_ssh_setup_failures_without_red_x() -> None:
    body = WORKFLOW.read_text()

    assert "set +e\n          ssh -o StrictHostKeyChecking=yes" in body
    assert 'smoke_pipe_status=("${PIPESTATUS[@]}")' in body
    assert "set -e\n          smoke_exit=${smoke_pipe_status[0]:-1}" in body
    assert "smoke_state=setup_pending" in body


def test_kis_smoke_helper_does_not_retry_full_live_tests_after_failure() -> None:
    body = HELPER.read_text()

    assert "재시도: 직접 uv 호출" not in body
    assert "not retrying full live tests" in body
    assert body.count("tests/integration/test_live_broker.py -v -s") == 1


def test_live_broker_token_bundle_repr_masks_fixture_secrets() -> None:
    spec = importlib.util.spec_from_file_location("live_broker_smoke", LIVE_BROKER)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    bundle = module._KisTokenBundle(
        {
            "access_token": "token-secret",
            "token_type": "Bearer",
            "app_key": "app-key-secret",
            "app_secret": "app-secret-value",
        }
    )

    rendered = repr(bundle)

    assert "token-secret" not in rendered
    assert "app-key-secret" not in rendered
    assert "app-secret-value" not in rendered
    assert rendered.count("[REDACTED]") == 3
    assert "Bearer" in rendered
