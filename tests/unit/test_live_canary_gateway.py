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
        "  if [[ \"${FAKE_EXPECT_RETRY_LEDGER:-0}\" == '1' ]]; then\n"
        "    [[ -s \"${FAKE_RETRY_LEDGER}\" ]] || exit 98\n"
        "  fi\n"
        "  if [[ \"${FAKE_REBALANCE_EXIT:-0}\" != '0' ]]; then\n"
        "    exit \"${FAKE_REBALANCE_EXIT}\"\n"
        "  fi\n"
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


def _write_retry_incident(
    gateway_env: dict[str, object],
    tmp_path: Path,
    *,
    first_source: str = "server_timer",
    first_state: str = "REJECTED_BY_BROKER",
    reconciliation_status: str = "OK",
    evidence_quality: str = "VALID",
    halt: bool = False,
    open_unfilled: int = 0,
    manifest_enabled: bool = True,
    manifest_msg_code: str = "APBK1672",
    summary_orders_submitted: int = 0,
    extra_planned_order: bool = False,
    remediation_override: str | None = None,
) -> tuple[str, str, str]:
    repo = gateway_env["repo"]
    assert isinstance(repo, Path)
    env = gateway_env["env"]
    assert isinstance(env, dict)
    state = Path(str(env["NONCE_DIR"]))
    env["FAKE_EXPECT_RETRY_LEDGER"] = "1"
    env["FAKE_RETRY_LEDGER"] = str(state / "order-session-retries.tsv")
    session = "2026-08-31"
    first_run_id = "20260831143500"
    retry_run_id = "20260831144700"
    first_code = _run("git", "rev-parse", "HEAD", cwd=repo).stdout.strip()

    (repo / "README.md").write_text("remediated\n", encoding="utf-8")
    _run("git", "add", "README.md", cwd=repo)
    _run("git", "commit", "-qm", "remediation", cwd=repo)
    remediation = _run("git", "rev-parse", "HEAD", cwd=repo).stdout.strip()

    signatures = [
        {
            "symbol": "SCHX",
            "kis_rt_cd": "7",
            "kis_msg_cd": "APBK1672",
            "http_status": 200,
            "exception_type": "KisOrderResponseError",
            "tr_id": "TTTT1002U",
            "order_exchange": "AMEX",
            "order_division": "00",
        }
    ]
    manifest = {
        "schema_version": "1.0",
        "incident_id": "kis-order-protocol-2026-08-31",
        "enabled": manifest_enabled,
        "market_session": session,
        "first_run_id": first_run_id,
        "first_source": first_source,
        "first_code_commit": first_code,
        "remediation_commit": remediation_override or remediation,
        "broker_rejection_signatures": [
            {**signatures[0], "kis_msg_cd": manifest_msg_code}
        ],
    }
    deploy = repo / "deploy"
    deploy.mkdir()
    (deploy / "live-canary-retry-incident.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    _run("git", "add", "deploy/live-canary-retry-incident.json", cwd=repo)
    _run("git", "commit", "-qm", "incident manifest", cwd=repo)
    current = _run("git", "rev-parse", "HEAD", cwd=repo).stdout.strip()

    state.mkdir(parents=True)
    (state / "order-sessions.tsv").write_text(
        f"{session}\t{first_run_id}\t{first_code}\t2026-08-31T14:35:00Z\t{first_source}\n",
        encoding="utf-8",
    )
    run_dir = state / "scheduled-runs" / first_run_id
    run_dir.mkdir(parents=True)
    reason = {
        "exception_type": "KisOrderResponseError",
        "http_status": 200,
        "kis_rt_cd": "7",
        "kis_msg_cd": "APBK1672",
        "request_summary": {
            "tr_id": "TTTT1002U",
            "body": {"OVRS_EXCG_CD": "AMEX", "ORD_DVSN": "00"},
        },
    }
    routed_qty = 0 if first_state == "SUBMISSION_UNKNOWN" else 2
    planned_orders = [{"symbol": "SCHX", "side": "BUY", "qty": 2}]
    if extra_planned_order:
        planned_orders.append({"symbol": "IAUM", "side": "BUY", "qty": 1})
    order_payload = {
        "fundability": {
            "planned_orders": planned_orders
        },
        "results": [
            {
                "symbol": "SCHX",
                "side": "BUY",
                "requested_qty": 2,
                "routed_qty": routed_qty,
                "limit_price_usd": "30.20",
                "state": first_state,
                "gate": None,
                "reason": json.dumps(reason),
            }
        ],
        "withheld_orders": [],
    }
    (run_dir / "order.log").write_text(
        json.dumps(order_payload) + "\n", encoding="utf-8"
    )
    summary = {
        "schema_version": "1.1",
        "run_id": first_run_id,
        "source": "server_timer",
        "market_session": session,
        "started_at_utc": "2026-08-31T14:35:00Z",
        "finished_at_utc": "2026-08-31T14:36:00Z",
        "code_commit": first_code,
        "deployed_code_commit": first_code,
        "operational_equivalent": True,
        "capital_usd": "293",
        "entry_state": "ENTRY_READY",
        "entry_allowed": True,
        "claim_status": "claimed",
        "order_exit": 0,
        "orders_submitted": summary_orders_submitted,
        "fills_exit": 0,
        "measurement_exit": 0,
        "reconciliation_exit": 0,
        "result": "completed",
    }
    (run_dir / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    reconciliation = {
        "status": "CLEAR",
        "reconciliation_state": reconciliation_status,
        "evidence_quality": evidence_quality,
        "halt_present_before": halt,
        "halt_present_after": halt,
        "orders_submitted": 0,
    }
    (run_dir / "reconciliation.json").write_text(
        json.dumps(reconciliation), encoding="utf-8"
    )
    for path in run_dir.iterdir():
        path.chmod(0o600)

    smoke = tmp_path / "kis-smoke"
    smoke.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        f"printf '%s\\n' 'open_unfilled={open_unfilled}'\n",
        encoding="utf-8",
    )
    smoke.chmod(0o755)
    env["KIS_SMOKE_HELPER"] = str(smoke)
    env["FAKE_SESSION_KEY"] = session
    return current, first_run_id, retry_run_id


def _claim_server_retry(
    gateway_env: dict[str, object],
    tmp_path: Path,
    *,
    current: str,
    retry_run_id: str,
    source: str = "server_timer",
) -> subprocess.CompletedProcess[str]:
    env = gateway_env["env"]
    assert isinstance(env, dict)
    library = tmp_path / "live-canary-library.sh"
    helper_text = HELPER.read_text(encoding="utf-8").rsplit('\nmain "$@"', 1)[0]
    helper_text = helper_text.replace(
        "/usr/local/sbin/auto-invest-kis-smoke", str(env["KIS_SMOKE_HELPER"])
    )
    library.write_text(
        helper_text,
        encoding="utf-8",
    )
    return subprocess.run(
        [
            "bash",
            "-c",
            'source "$1"; file_owned_by_root() { return 0; }; cd "$REPO"; '
            'place_order_authorized "$4" "$2" "$3" 293',
            "retry-test",
            str(library),
            retry_run_id,
            current,
            source,
        ],
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )


def test_exact_zero_acceptance_server_incident_gets_one_separate_retry_claim(
    gateway_env: dict[str, object], tmp_path: Path
) -> None:
    current, first_run_id, retry_run_id = _write_retry_incident(
        gateway_env, tmp_path
    )
    env = gateway_env["env"]
    assert isinstance(env, dict)
    state = Path(str(env["NONCE_DIR"]))
    session_before = (state / "order-sessions.tsv").read_text(encoding="utf-8")

    first = _claim_server_retry(
        gateway_env,
        tmp_path,
        current=current,
        retry_run_id=retry_run_id,
    )
    second = _claim_server_retry(
        gateway_env,
        tmp_path,
        current=current,
        retry_run_id="20260831145900",
    )

    assert first.returncode == 0, first.stderr
    assert "LIVE_ORDER_SESSION_RETRY_CLAIMED" in first.stdout
    assert f"first_run_id={first_run_id}" in first.stdout
    assert second.returncode == 0, second.stderr
    assert "LIVE_ORDER_SESSION_ALREADY_CLAIMED" in second.stdout
    assert f"retry_run_id={retry_run_id}" in second.stdout
    assert (state / "order-sessions.tsv").read_text(encoding="utf-8") == session_before
    retry_rows = (state / "order-session-retries.tsv").read_text(
        encoding="utf-8"
    )
    assert retry_rows.count("\n") == 1
    assert retry_run_id in retry_rows
    uv_log = gateway_env["uv_log"]
    assert isinstance(uv_log, Path)
    assert uv_log.read_text(encoding="utf-8").count("auto-invest rebalance-once") == 1


@pytest.mark.parametrize(
    ("override", "value"),
    [
        ("first_state", "SUBMISSION_UNKNOWN"),
        ("first_state", "SUBMITTED"),
        ("first_state", "PARTIALLY_FILLED"),
        ("first_state", "FILLED"),
        ("reconciliation_status", "MISMATCH"),
        ("evidence_quality", "INVALID"),
        ("halt", True),
        ("open_unfilled", 1),
        ("first_source", "github_schedule"),
        ("manifest_enabled", False),
        ("manifest_msg_code", "APBK9999"),
        ("summary_orders_submitted", 1),
        ("extra_planned_order", True),
        ("remediation_override", "f" * 40),
    ],
)
def test_same_session_retry_fails_closed_on_ambiguous_or_unsafe_evidence(
    gateway_env: dict[str, object],
    tmp_path: Path,
    override: str,
    value: str | bool | int,
) -> None:
    kwargs = {override: value}
    current, _, retry_run_id = _write_retry_incident(
        gateway_env, tmp_path, **kwargs
    )
    result = _claim_server_retry(
        gateway_env,
        tmp_path,
        current=current,
        retry_run_id=retry_run_id,
    )
    env = gateway_env["env"]
    assert isinstance(env, dict)
    retry_file = Path(str(env["NONCE_DIR"])) / "order-session-retries.tsv"

    assert result.returncode == 0, result.stderr
    assert "LIVE_ORDER_SESSION_ALREADY_CLAIMED" in result.stdout
    assert "LIVE_ORDER_SESSION_RETRY_CLAIMED" not in result.stdout
    assert not retry_file.exists() or retry_file.read_text(encoding="utf-8") == ""
    uv_log = gateway_env["uv_log"]
    assert isinstance(uv_log, Path)
    assert not uv_log.exists() or "auto-invest rebalance-once" not in uv_log.read_text(
        encoding="utf-8"
    )


def test_same_session_retry_requires_manifest_tracked_by_deployed_code(
    gateway_env: dict[str, object], tmp_path: Path
) -> None:
    current, _, retry_run_id = _write_retry_incident(gateway_env, tmp_path)
    repo = gateway_env["repo"]
    assert isinstance(repo, Path)
    (repo / "deploy" / "live-canary-retry-incident.json").unlink()
    _run("git", "add", "deploy/live-canary-retry-incident.json", cwd=repo)
    _run("git", "commit", "-qm", "remove incident manifest", cwd=repo)
    current = _run("git", "rev-parse", "HEAD", cwd=repo).stdout.strip()

    result = _claim_server_retry(
        gateway_env,
        tmp_path,
        current=current,
        retry_run_id=retry_run_id,
    )

    assert result.returncode == 0, result.stderr
    assert "LIVE_ORDER_SESSION_ALREADY_CLAIMED" in result.stdout
    assert "LIVE_ORDER_SESSION_RETRY_CLAIMED" not in result.stdout


def test_signed_github_schedule_cannot_consume_server_retry_slot(
    gateway_env: dict[str, object], tmp_path: Path
) -> None:
    current, _, retry_run_id = _write_retry_incident(gateway_env, tmp_path)
    result = _claim_server_retry(
        gateway_env,
        tmp_path,
        current=current,
        retry_run_id=retry_run_id,
        source="github_schedule",
    )

    assert result.returncode == 0, result.stderr
    assert "LIVE_ORDER_SESSION_ALREADY_CLAIMED" in result.stdout
    assert "LIVE_ORDER_SESSION_RETRY_CLAIMED" not in result.stdout


def test_failed_retry_still_consumes_the_only_same_session_slot(
    gateway_env: dict[str, object], tmp_path: Path
) -> None:
    current, _, retry_run_id = _write_retry_incident(gateway_env, tmp_path)
    env = gateway_env["env"]
    assert isinstance(env, dict)
    env["FAKE_REBALANCE_EXIT"] = "42"

    failed = _claim_server_retry(
        gateway_env,
        tmp_path,
        current=current,
        retry_run_id=retry_run_id,
    )
    env["FAKE_REBALANCE_EXIT"] = "0"
    duplicate = _claim_server_retry(
        gateway_env,
        tmp_path,
        current=current,
        retry_run_id="20260831145900",
    )
    env["FAKE_SESSION_KEY"] = "2026-09-01"
    env["FAKE_EXPECT_RETRY_LEDGER"] = "0"
    next_session = _claim_server_retry(
        gateway_env,
        tmp_path,
        current=current,
        retry_run_id="20260901143500",
    )
    uv_log = gateway_env["uv_log"]
    assert isinstance(uv_log, Path)

    assert failed.returncode == 42
    assert "LIVE_ORDER_SESSION_RETRY_CLAIMED" in failed.stdout
    assert duplicate.returncode == 0, duplicate.stderr
    assert "LIVE_ORDER_SESSION_ALREADY_CLAIMED" in duplicate.stdout
    assert f"retry_run_id={retry_run_id}" in duplicate.stdout
    assert next_session.returncode == 0, next_session.stderr
    assert "LIVE_ORDER_SESSION_CLAIMED" in next_session.stdout
    assert uv_log.read_text(encoding="utf-8").count("auto-invest rebalance-once") == 2


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


def test_scheduled_status_binds_retry_summary_to_first_and_retry_ids(
    gateway_env: dict[str, object],
) -> None:
    env = gateway_env["env"]
    assert isinstance(env, dict)
    state = Path(str(env["NONCE_DIR"]))
    run_id = "20260901144700"
    first_run_id = "20260901143500"
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
        "claim_status": "retry_claimed",
        "attempt_kind": "same_session_retry",
        "first_run_id": first_run_id,
        "retry_run_id": run_id,
    }
    summary_path = run_dir / "summary.json"
    summary_path.write_text(json.dumps(summary), encoding="utf-8")

    accepted = subprocess.run(
        ["bash", str(HELPER), "scheduled-status", run_id],
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    summary["retry_run_id"] = first_run_id
    summary_path.write_text(json.dumps(summary), encoding="utf-8")
    rejected = subprocess.run(
        ["bash", str(HELPER), "scheduled-status", run_id],
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )

    assert accepted.returncode == 0, accepted.stderr
    assert json.loads(accepted.stdout)["first_run_id"] == first_run_id
    assert rejected.returncode == 2
    assert "invalid scheduled run summary" in rejected.stderr


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
        "schema_version": "1.3",
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
        "kis_msg1": (
            "계좌 12345678은 해외주식 서비스 미신청으로 주문 권한이 제한됩니다 "
            "token=must-not-leak"
        ),
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
            "message_topics": [
                "account",
                "service_registration",
                "trading_permission",
            ],
            "service_registration_scopes": ["overseas_securities"],
        }
    ]
    assert "must-not-leak" not in result.stdout
    assert "12345678" not in result.stdout
    assert "계좌" not in result.stdout
    assert "미신청" not in result.stdout
    assert "30.20" not in result.stdout
    assert "******78" not in result.stdout


def test_scheduled_order_diagnostics_uses_closed_fallback_message_topics(
    gateway_env: dict[str, object],
) -> None:
    env = gateway_env["env"]
    assert isinstance(env, dict)
    state = Path(str(env["NONCE_DIR"]))
    run_id = "20260904152303"
    run_dir = state / "scheduled-runs" / run_id
    run_dir.mkdir(parents=True)
    reasons = [
        {"kis_msg1": "해외ETP 거래 서비스 미신청 계좌"},
        {"kis_msg1": "해외변동성ETN 약정 미등록"},
        {"kis_msg1": "별도 서비스 등록 필요"},
        {"kis_msg1": "주문 가능 금액 부족"},
        {"kis_msg1": "분류되지 않은 내부 사유 secret-token"},
        {},
    ]
    raw = {
        "fundability": {"planned_orders": []},
        "results": [
            {
                "symbol": symbol,
                "side": "BUY",
                "requested_qty": 1,
                "routed_qty": 1,
                "limit_price_usd": "1.00",
                "state": "REJECTED_BY_BROKER",
                "gate": None,
                "reason": json.dumps(reason),
            }
            for symbol, reason in zip(
                ("AAA", "BBB", "CCC", "DDD", "EEE", "FFF"),
                reasons,
                strict=True,
            )
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
    assert [row["message_topics"] for row in payload["broker_rejections"]] == [
        ["account", "service_registration"],
        ["service_registration"],
        ["service_registration"],
        ["buying_power"],
        ["other"],
        ["unavailable"],
    ]
    assert [
        row["service_registration_scopes"]
        for row in payload["broker_rejections"]
    ] == [
        ["overseas_etp"],
        ["overseas_volatility_etn"],
        ["generic_service"],
        ["not_applicable"],
        ["not_applicable"],
        ["unavailable"],
    ]
    assert "해외ETP" not in result.stdout
    assert "해외변동성ETN" not in result.stdout
    assert "주문 가능 금액" not in result.stdout
    assert "secret-token" not in result.stdout


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
