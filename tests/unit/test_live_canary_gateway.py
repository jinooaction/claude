"""Spec 143: signed production live-canary gateway contract."""

from __future__ import annotations

import base64
import os
import subprocess
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HELPER = ROOT / "deploy" / "live-canary-on-instance.sh"
REPOSITORY = "jinooaction/claude"
WORKFLOW = "rebalance-live-canary.yml"


def _run(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(args),
        cwd=cwd,
        text=True,
        capture_output=True,
        check=True,
    )


@pytest.fixture
def gateway_env(tmp_path: Path) -> dict[str, object]:
    repo = tmp_path / "repo"
    repo.mkdir()
    _run("git", "init", "-q", cwd=repo)
    _run("git", "config", "user.name", "test", cwd=repo)
    _run("git", "config", "user.email", "test@example.com", cwd=repo)
    (repo / "automation").mkdir()
    sentinel = repo / "automation" / "rebalance-live.request"
    sentinel.write_text(
        "armed: true\ncapital_usd: 293\nladder_rung: 1\naccount_nav_usd: 1466.83\n",
        encoding="utf-8",
    )
    (repo / "README.md").write_text("test\n", encoding="utf-8")
    _run("git", "add", ".", cwd=repo)
    _run("git", "commit", "-qm", "base", cwd=repo)
    _run("git", "remote", "add", "origin", str(repo), cwd=repo)

    private_key = tmp_path / "private.pem"
    public_key = tmp_path / "public.pem"
    _run("openssl", "genpkey", "-algorithm", "ED25519", "-out", str(private_key))
    _run(
        "openssl",
        "pkey",
        "-in",
        str(private_key),
        "-pubout",
        "-out",
        str(public_key),
    )

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    sudo = fake_bin / "sudo"
    sudo.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "if [[ \"${1:-}\" == \"-u\" ]]; then shift 2; fi\n"
        "if [[ \"${1:-}\" == \"-H\" ]]; then shift; fi\n"
        "exec \"$@\"\n",
        encoding="utf-8",
    )
    sudo.chmod(0o755)
    flock = fake_bin / "flock"
    flock.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    flock.chmod(0o755)

    env = os.environ.copy()
    env.update(
        {
            "REPO": str(repo),
            "PUBLIC_KEY": str(public_key),
            "NONCE_DIR": str(tmp_path / "nonces"),
            "PATH": f"{fake_bin}:{env['PATH']}",
        }
    )
    return {
        "repo": repo,
        "sentinel": sentinel,
        "private_key": private_key,
        "env": env,
    }


def _signature(
    tmp_path: Path,
    private_key: Path,
    *,
    run_id: str,
    sha: str,
    capital: str,
    expires: str,
    nonce: str,
) -> str:
    payload = (
        f"{REPOSITORY}|{WORKFLOW}|{run_id}|{sha}|{capital}|{expires}|{nonce}"
    )
    payload_path = tmp_path / f"payload-{nonce}"
    signature_path = tmp_path / f"signature-{nonce}"
    payload_path.write_text(payload, encoding="ascii")
    _run(
        "openssl",
        "pkeyutl",
        "-sign",
        "-rawin",
        "-inkey",
        str(private_key),
        "-in",
        str(payload_path),
        "-out",
        str(signature_path),
    )
    return base64.b64encode(signature_path.read_bytes()).decode("ascii")


def _verify(
    gateway_env: dict[str, object],
    tmp_path: Path,
    *,
    run_id: str = "31999999999",
    capital: str = "293",
    expires: str | None = None,
    nonce: str = "31999999999-1",
    signature: str | None = None,
) -> subprocess.CompletedProcess[str]:
    repo = gateway_env["repo"]
    assert isinstance(repo, Path)
    private_key = gateway_env["private_key"]
    assert isinstance(private_key, Path)
    sha = _run("git", "rev-parse", "HEAD", cwd=repo).stdout.strip()
    expiry = expires or str(int(time.time()) + 300)
    signed = signature or _signature(
        tmp_path,
        private_key,
        run_id=run_id,
        sha=sha,
        capital=capital,
        expires=expiry,
        nonce=nonce,
    )
    env = gateway_env["env"]
    assert isinstance(env, dict)
    return subprocess.run(
        [
            "bash",
            str(HELPER),
            "verify-order",
            run_id,
            sha,
            capital,
            expiry,
            nonce,
            signed,
        ],
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )


def test_signed_order_request_is_authorized_once(
    gateway_env: dict[str, object], tmp_path: Path
) -> None:
    first = _verify(gateway_env, tmp_path)
    replay = _verify(gateway_env, tmp_path)

    assert first.returncode == 0
    assert "LIVE_ORDER_AUTHORIZED" in first.stdout
    assert replay.returncode == 2
    assert "nonce already used" in replay.stderr


def test_tampered_signature_is_rejected(
    gateway_env: dict[str, object], tmp_path: Path
) -> None:
    result = _verify(gateway_env, tmp_path, signature=base64.b64encode(b"bad").decode())

    assert result.returncode == 2
    assert "signature verification failed" in result.stderr


def test_expired_signature_is_rejected_before_nonce_consumption(
    gateway_env: dict[str, object], tmp_path: Path
) -> None:
    result = _verify(gateway_env, tmp_path, expires=str(int(time.time()) - 1))

    assert result.returncode == 2
    assert "signature expired" in result.stderr


@pytest.mark.parametrize(
    ("sentinel_text", "reason"),
    [
        (
            "armed: false\ncapital_usd: 293\nladder_rung: 1\naccount_nav_usd: 1466.83\n",
            "not armed",
        ),
        (
            "armed: true\ncapital_usd: 294\nladder_rung: 1\naccount_nav_usd: 1466.83\n",
            "does not match sentinel",
        ),
    ],
)
def test_sentinel_authority_mismatch_is_rejected(
    gateway_env: dict[str, object],
    tmp_path: Path,
    sentinel_text: str,
    reason: str,
) -> None:
    sentinel = gateway_env["sentinel"]
    assert isinstance(sentinel, Path)
    sentinel.write_text(sentinel_text, encoding="utf-8")
    result = _verify(gateway_env, tmp_path)

    assert result.returncode == 2
    assert reason in result.stderr


def test_gateway_exposes_signed_order_and_non_order_evidence_only() -> None:
    repair = (ROOT / "deploy" / "repair-ssh-boundary.sh").read_text(encoding="utf-8")
    helper = HELPER.read_text(encoding="utf-8")

    assert "live-canary-order\\ *)" in repair
    assert "live-canary-verify-order\\ *)" in repair
    assert "auto-invest-live-canary verify-order" in repair
    assert "live-canary-fills)" in repair
    assert "live-canary-profit\\ *)" in repair
    assert "verify_signature" in helper
    assert "consume_nonce" in helper
    assert "--mode live" in helper
    assert "--confirm-live" in helper
    assert "performance" in helper
    assert "--snapshot" in helper
