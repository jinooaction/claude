"""Spec 143: signed production live-canary gateway contract."""

from __future__ import annotations

import base64
import json
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
    uv_log = tmp_path / "uv.log"
    uv = fake_bin / "uv"
    uv.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "printf '%s\\n' \"$*\" >> \"${FAKE_UV_LOG}\"\n"
        "if [[ \"$*\" == *'python -m auto_invest.execution.live_session'* ]]; then\n"
        "  if [[ \"${FAKE_SESSION_EXIT:-0}\" != '0' ]]; then\n"
        "    exit \"${FAKE_SESSION_EXIT}\"\n"
        "  fi\n"
        "  printf '%s\\n' \"${FAKE_SESSION_KEY:-2026-08-31}\"\n"
        "  exit 0\n"
        "fi\n"
        "if [[ \"$*\" == *'auto-invest rebalance-once'* ]]; then\n"
        "  printf '%s\\n' '{\"results\": []}'\n"
        "  exit 0\n"
        "fi\n"
        "exit 99\n",
        encoding="utf-8",
    )
    uv.chmod(0o755)

    broker_write_lock = tmp_path / "broker-write.lock"
    broker_write_lock.touch()

    env = os.environ.copy()
    env.update(
        {
            "REPO": str(repo),
            "PUBLIC_KEY": str(public_key),
            "NONCE_DIR": str(tmp_path / "nonces"),
            "UV_BIN": str(uv),
            "FAKE_UV_LOG": str(uv_log),
            "BROKER_WRITE_LOCK_PATH": str(broker_write_lock),
            "DEPLOY_MAINTENANCE_INTERLOCK": str(
                tmp_path / "live-order-maintenance.lock"
            ),
            "PATH": f"{fake_bin}:{env['PATH']}",
        }
    )
    return {
        "repo": repo,
        "sentinel": sentinel,
        "private_key": private_key,
        "uv_log": uv_log,
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


def _order(
    gateway_env: dict[str, object],
    tmp_path: Path,
    *,
    run_id: str,
    nonce: str,
) -> subprocess.CompletedProcess[str]:
    repo = gateway_env["repo"]
    assert isinstance(repo, Path)
    private_key = gateway_env["private_key"]
    assert isinstance(private_key, Path)
    sha = _run("git", "rev-parse", "HEAD", cwd=repo).stdout.strip()
    expiry = str(int(time.time()) + 300)
    signed = _signature(
        tmp_path,
        private_key,
        run_id=run_id,
        sha=sha,
        capital="293",
        expires=expiry,
        nonce=nonce,
    )
    env = gateway_env["env"]
    assert isinstance(env, dict)
    return subprocess.run(
        [
            "bash",
            str(HELPER),
            "order",
            run_id,
            sha,
            "293",
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


def test_market_session_allows_exactly_one_order_command(
    gateway_env: dict[str, object], tmp_path: Path
) -> None:
    first = _order(
        gateway_env,
        tmp_path,
        run_id="31999999991",
        nonce="31999999991-1",
    )
    duplicate = _order(
        gateway_env,
        tmp_path,
        run_id="31999999992",
        nonce="31999999992-1",
    )
    uv_log = gateway_env["uv_log"]
    assert isinstance(uv_log, Path)

    assert first.returncode == 0, first.stderr
    assert "LIVE_ORDER_SESSION_CLAIMED" in first.stdout
    assert duplicate.returncode == 0, duplicate.stderr
    assert "LIVE_ORDER_SESSION_ALREADY_CLAIMED" in duplicate.stdout
    assert "first_run_id=31999999991" in duplicate.stdout
    assert "first_source=github_schedule" in duplicate.stdout
    assert uv_log.read_text(encoding="utf-8").count("auto-invest rebalance-once") == 1


def test_closed_session_does_not_consume_daily_order_claim(
    gateway_env: dict[str, object], tmp_path: Path
) -> None:
    env = gateway_env["env"]
    assert isinstance(env, dict)
    env["FAKE_SESSION_EXIT"] = "75"

    result = _order(
        gateway_env,
        tmp_path,
        run_id="31999999993",
        nonce="31999999993-1",
    )
    uv_log = gateway_env["uv_log"]
    assert isinstance(uv_log, Path)

    assert result.returncode == 75
    assert not uv_log.exists() or "auto-invest rebalance-once" not in uv_log.read_text(
        encoding="utf-8"
    )
    session_file = Path(str(env["NONCE_DIR"])) / "order-sessions.tsv"
    assert not session_file.exists() or session_file.read_text(encoding="utf-8") == ""


def test_next_market_session_gets_a_new_single_order_command(
    gateway_env: dict[str, object], tmp_path: Path
) -> None:
    first = _order(
        gateway_env,
        tmp_path,
        run_id="31999999994",
        nonce="31999999994-1",
    )
    env = gateway_env["env"]
    assert isinstance(env, dict)
    env["FAKE_SESSION_KEY"] = "2026-09-01"
    second = _order(
        gateway_env,
        tmp_path,
        run_id="31999999995",
        nonce="31999999995-1",
    )
    uv_log = gateway_env["uv_log"]
    assert isinstance(uv_log, Path)

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    assert uv_log.read_text(encoding="utf-8").count("auto-invest rebalance-once") == 2


def test_scheduled_status_reads_only_fixed_latest_server_summary(
    gateway_env: dict[str, object],
) -> None:
    env = gateway_env["env"]
    assert isinstance(env, dict)
    state = Path(str(env["NONCE_DIR"]))
    run_id = "20260901143500"
    run_dir = state / "scheduled-runs" / run_id
    run_dir.mkdir(parents=True)
    summary = {
        "schema_version": "1.1",
        "run_id": run_id,
        "source": "server_timer",
        "market_session": "2026-09-01",
        "code_commit": "b" * 40,
        "deployed_code_commit": "a" * 40,
        "operational_equivalent": True,
    }
    (run_dir / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    (state / "last-scheduled-run-id").write_text(f"{run_id}\n", encoding="utf-8")

    result = subprocess.run(
        ["bash", str(HELPER), "scheduled-status"],
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == summary

    explicit = subprocess.run(
        ["bash", str(HELPER), "scheduled-status", run_id],
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    assert explicit.returncode == 0, explicit.stderr
    assert json.loads(explicit.stdout) == summary


def test_scheduled_status_rejects_pointer_symlink(
    gateway_env: dict[str, object], tmp_path: Path
) -> None:
    env = gateway_env["env"]
    assert isinstance(env, dict)
    state = Path(str(env["NONCE_DIR"]))
    state.mkdir(parents=True)
    target = tmp_path / "untrusted-pointer"
    target.write_text("20260901143500\n", encoding="utf-8")
    (state / "last-scheduled-run-id").symlink_to(target)

    result = subprocess.run(
        ["bash", str(HELPER), "scheduled-status"],
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )

    assert result.returncode == 2
    assert "no server-scheduled live canary evidence" in result.stderr


def test_scheduled_order_diagnostics_exposes_only_closed_safe_fields(
    gateway_env: dict[str, object],
) -> None:
    env = gateway_env["env"]
    assert isinstance(env, dict)
    state = Path(str(env["NONCE_DIR"]))
    run_id = "20260903161106"
    run_dir = state / "scheduled-runs" / run_id
    run_dir.mkdir(parents=True)
    raw = {
        "portfolio_id": "secret-portfolio",
        "purchasable_cash_usd": "934.27",
        "fundability": {
            "planned_orders": [{"symbol": "SCHX", "side": "BUY", "qty": 2}]
        },
        "results": [
            {
                "symbol": "SCHX",
                "side": "BUY",
                "requested_qty": 2,
                "routed_qty": 2,
                "limit_price_usd": "30.20",
                "state": "REJECTED_BY_GATE",
                "gate": "global_exposure_gate",
                "reason": "account=must-not-leak token=must-not-leak",
            }
        ],
        "withheld_orders": [
            {
                "symbol": "ORANY",
                "side": "SELL",
                "requested_qty": 28,
                "reason": "unmanaged_holding",
            }
        ],
    }
    (run_dir / "order.log").write_text(
        "LIVE_ORDER_SESSION_CLAIMED market_session=2026-09-03\n"
        + json.dumps(raw)
        + "\n",
        encoding="utf-8",
    )
    (state / "last-scheduled-run-id").write_text(f"{run_id}\n", encoding="utf-8")

    result = subprocess.run(
        ["bash", str(HELPER), "scheduled-order-diagnostics"],
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload == {
        "schema_version": "1.1",
        "source": "server_timer_order_diagnostics",
        "run_id": run_id,
        "planned_order_count": 1,
        "result_count": 1,
        "withheld_order_count": 1,
        "outcomes": [
            {
                "symbol": "SCHX",
                "side": "BUY",
                "requested_qty": 2,
                "routed_qty": 2,
                "state": "REJECTED_BY_GATE",
                "gate": "global_exposure_gate",
            }
        ],
        "broker_rejections": [],
        "withheld_reason_codes": ["unmanaged_holding"],
    }
    assert "must-not-leak" not in result.stdout
    assert "934.27" not in result.stdout
    assert "30.20" not in result.stdout


def test_scheduled_order_diagnostics_exposes_only_closed_broker_codes(
    gateway_env: dict[str, object],
) -> None:
    env = gateway_env["env"]
    assert isinstance(env, dict)
    state = Path(str(env["NONCE_DIR"]))
    run_id = "20260903161106"
    run_dir = state / "scheduled-runs" / run_id
    run_dir.mkdir(parents=True)
    broker_reason = {
        "exception_type": "KisOrderResponseError",
        "http_status": 200,
        "kis_rt_cd": "7",
        "kis_msg_cd": "APBK1672",
        "kis_msg1": "must-not-leak",
        "response_body_preview": "account=must-not-leak",
        "request_summary": {
            "tr_id": "TTTT1002U",
            "body": {
                "OVRS_EXCG_CD": "NASD",
                "ORD_DVSN": "00",
                "OVRS_ORD_UNPR": "30.20",
                "CANO": "******78",
            },
        },
    }
    raw = {
        "fundability": {
            "planned_orders": [{"symbol": "SCHX", "side": "BUY", "qty": 2}]
        },
        "results": [
            {
                "symbol": "SCHX",
                "side": "BUY",
                "requested_qty": 2,
                "routed_qty": 2,
                "limit_price_usd": "30.20",
                "state": "REJECTED_BY_BROKER",
                "gate": None,
                "reason": json.dumps(broker_reason),
            }
        ],
        "withheld_orders": [],
    }
    (run_dir / "order.log").write_text(json.dumps(raw) + "\n", encoding="utf-8")

    result = subprocess.run(
        ["bash", str(HELPER), "scheduled-order-diagnostics", run_id],
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["broker_rejections"] == [
        {
            "symbol": "SCHX",
            "kis_rt_cd": "7",
            "kis_msg_cd": "APBK1672",
            "http_status": 200,
            "exception_type": "KisOrderResponseError",
            "tr_id": "TTTT1002U",
            "order_exchange": "NASD",
            "order_division": "00",
        }
    ]
    assert "must-not-leak" not in result.stdout
    assert "30.20" not in result.stdout
    assert "******78" not in result.stdout


def test_scheduled_order_diagnostics_fails_closed_on_unknown_broker_field(
    gateway_env: dict[str, object],
) -> None:
    env = gateway_env["env"]
    assert isinstance(env, dict)
    state = Path(str(env["NONCE_DIR"]))
    run_id = "20260903161106"
    run_dir = state / "scheduled-runs" / run_id
    run_dir.mkdir(parents=True)
    raw = {
        "fundability": {"planned_orders": []},
        "results": [
            {
                "symbol": "SCHX",
                "side": "BUY",
                "requested_qty": 2,
                "routed_qty": 2,
                "limit_price_usd": "30.20",
                "state": "REJECTED_BY_BROKER",
                "gate": None,
                "reason": json.dumps(
                    {
                        "kis_rt_cd": "7",
                        "kis_msg_cd": "APBK1672",
                        "request_summary": {
                            "tr_id": "TTTT1002U",
                            "body": {"OVRS_EXCG_CD": "SECRET", "ORD_DVSN": "00"},
                        },
                    }
                ),
            }
        ],
        "withheld_orders": [],
    }
    (run_dir / "order.log").write_text(json.dumps(raw) + "\n", encoding="utf-8")

    result = subprocess.run(
        ["bash", str(HELPER), "scheduled-order-diagnostics", run_id],
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )

    assert result.returncode == 2
    assert "invalid sanitized broker rejection diagnostics" in result.stderr
    assert "SECRET" not in result.stdout + result.stderr


def test_scheduled_order_diagnostics_fails_closed_on_unknown_state(
    gateway_env: dict[str, object],
) -> None:
    env = gateway_env["env"]
    assert isinstance(env, dict)
    state = Path(str(env["NONCE_DIR"]))
    run_id = "20260903161106"
    run_dir = state / "scheduled-runs" / run_id
    run_dir.mkdir(parents=True)
    raw = {
        "fundability": {"planned_orders": []},
        "results": [
            {
                "symbol": "SCHX",
                "side": "BUY",
                "requested_qty": 2,
                "routed_qty": 2,
                "limit_price_usd": "30.20",
                "state": "SECRET_UNKNOWN_STATE",
                "gate": None,
                "reason": "must-not-leak",
            }
        ],
        "withheld_orders": [],
    }
    (run_dir / "order.log").write_text(json.dumps(raw) + "\n", encoding="utf-8")

    result = subprocess.run(
        ["bash", str(HELPER), "scheduled-order-diagnostics", run_id],
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )

    assert result.returncode == 2
    assert "invalid scheduled order result" in result.stderr
    assert "must-not-leak" not in result.stdout + result.stderr


def test_runtime_status_reports_only_fixed_systemd_fields_and_sanitized_errors(
    gateway_env: dict[str, object],
) -> None:
    env = gateway_env["env"]
    assert isinstance(env, dict)
    fake_bin = Path(str(env["PATH"]).split(":", 1)[0])
    systemctl = fake_bin / "systemctl"
    systemctl.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "unit=${2:-}\n"
        "property=${3#--property=}\n"
        "case \"${unit}:${property}\" in\n"
        "  auto-invest-live-canary.timer:LoadState) echo loaded ;;\n"
        "  auto-invest-live-canary.timer:ActiveState) echo active ;;\n"
        "  auto-invest-live-canary.timer:LastTriggerUSec) "
        "echo 'Thu 2026-09-03 15:23:00 UTC' ;;\n"
        "  auto-invest-live-canary.timer:NextElapseUSecRealtime) "
        "echo 'Thu 2026-09-03 15:35:00 UTC' ;;\n"
        "  auto-invest-live-canary.service:LoadState) echo loaded ;;\n"
        "  auto-invest-live-canary.service:ActiveState) echo failed ;;\n"
        "  auto-invest-live-canary.service:Result) echo exit-code ;;\n"
        "  auto-invest-live-canary.service:ExecMainStatus) echo 2 ;;\n"
        "  auto-invest-live-canary.service:ExecMainStartTimestamp) "
        "echo 'Thu 2026-09-03 15:23:00 UTC' ;;\n"
        "  auto-invest-live-canary.service:ExecMainExitTimestamp) "
        "echo 'Thu 2026-09-03 15:23:01 UTC' ;;\n"
        "  *) exit 1 ;;\n"
        "esac\n",
        encoding="utf-8",
    )
    systemctl.chmod(0o755)
    journalctl = fake_bin / "journalctl"
    journalctl.write_text(
        "#!/usr/bin/env bash\n"
        "echo 'ERROR: TOKEN=must-not-leak'\n"
        "echo 'ERROR: server timer first-entry revalidation failed'\n",
        encoding="utf-8",
    )
    journalctl.chmod(0o755)

    result = subprocess.run(
        ["bash", str(HELPER), "runtime-status"],
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == "1.0"
    assert payload["source"] == "server_timer_runtime"
    assert payload["timer"]["active_state"] == "active"
    assert payload["service"]["result"] == "exit-code"
    assert payload["service"]["exec_main_status"] == 2
    assert payload["recent_events"] == [
        "unclassified_error",
        "first_entry_revalidation_failed",
    ]
    assert "must-not-leak" not in result.stdout


def test_direct_systemd_order_command_fails_before_claim_or_broker(
    gateway_env: dict[str, object],
) -> None:
    repo = gateway_env["repo"]
    assert isinstance(repo, Path)
    env = gateway_env["env"]
    assert isinstance(env, dict)
    sha = _run("git", "rev-parse", "HEAD", cwd=repo).stdout.strip()

    result = subprocess.run(
        [
            "bash",
            str(HELPER),
            "systemd-order",
            "20260901143500",
            sha,
            "293",
        ],
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )

    assert result.returncode == 2
    assert "systemd" in result.stderr or "requires root" in result.stderr
    uv_log = gateway_env["uv_log"]
    assert isinstance(uv_log, Path)
    assert not uv_log.exists() or "auto-invest rebalance-once" not in uv_log.read_text(
        encoding="utf-8"
    )
    session_file = Path(str(env["NONCE_DIR"])) / "order-sessions.tsv"
    assert not session_file.exists()


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
    assert "live-canary-scheduled-status)" in repair
    assert "live-canary-scheduled-status\\ *)" in repair
    assert "live-canary-runtime-status)" in repair
    assert "live-canary-scheduled-order-diagnostics)" in repair
    assert "live-canary-scheduled-order-diagnostics\\ *)" in repair
    gateway = repair.split("EOF_GATEWAY", 2)[1]
    assert "systemd-order" not in gateway
    assert "verify_signature" in helper
    assert "consume_nonce" in helper
    assert "claim_order_session" in helper
    assert "server_timer" in helper
    assert "scheduled-status" in helper
    assert "runtime-status" in helper
    assert "scheduled-order-diagnostics" in helper
    assert "server timer order is limited to ladder rung 1" in helper
    assert "server timer order requires operational_canary entry route" in helper
    assert "AUTOARM_DISABLED kill switch is active" in helper
    assert "python -m auto_invest.execution.live_session" in helper
    assert "--mode live" in helper
    assert "--confirm-live" in helper
    assert "performance" in helper
    assert "--snapshot" in helper
