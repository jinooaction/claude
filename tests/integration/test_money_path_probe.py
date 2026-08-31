"""스펙 052 — 첫-자본까지의 길 프로브 통합 테스트.

워크플로가 git show 로 만드는 사이드카 디렉터리(<key>.md)를 실제 LAST_RUN.md 형식으로
흉내 내, 프로브가 라벨된 JSON 블록을 뽑아 종합·출력하는지 검증한다. scripts/ 는
패키지가 아니므로 파일 경로로 직접 로드한다(실제 진입점 검증).

사이드카 JSON 은 런타임 json.dumps 로 만든다(실데이터처럼 단일 줄 JSON, 소스 줄은 짧게).
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_PROBE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "money_path_probe.py"
_spec = importlib.util.spec_from_file_location("money_path_probe", _PROBE_PATH)
assert _spec and _spec.loader
_probe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_probe)
probe_main = _probe.main


def _block(header: str, obj: dict) -> str:
    return f"## {header}\n```json\n{json.dumps(obj, ensure_ascii=False)}\n```\n"


def _edge_sidecar(n_obs: int = 1, legacy=None, snapshots=None, anchored=None) -> str:
    ladder = {
        "schema_version": "1.0",
        "action": "WAIT_EDGE",
        "current_rung": 0,
        "target_rung": 0,
        "reason": "단 0 + forward INSUFFICIENT_DATA",
        "account_nav_usd": "1518.21000000",
        "target_capital_usd": None,
        "live_dd_pct": "0.000000",
        "live_obs": 3,
    }
    verdict = {
        "schema_version": "1.1",
        "verdict": "INSUFFICIENT_DATA",
        "n_obs": n_obs,
        "min_obs_required": 20,
        "beats_benchmark_calmar": False,
        "dsr": None,
        "dsr_threshold": "0.95",
        "universe": ["SPY", "IEF", "GLD"],
    }
    if legacy is not None:
        verdict["legacy_snapshots_excluded"] = legacy
    if snapshots is not None:
        verdict["snapshot_count"] = snapshots
    growth = {
        "schema_version": "1.0",
        "mode": "live",
        "snapshot_count": 3,
        "current_nav_usd": "500.0",
        "period_days": "1.25",
    }
    text = (
        "# 자본 사다리 게이트 — 최신 실행\n\n"
        "| 항목 | 값 |\n|------|-----|\n"
        "| timestamp_utc | 2026-06-13T01:53:50Z |\n\n"
        + _block("결정 JSON", ladder)
        + "\n"
        + _block("forward 판정 JSON (검증된 앙상블, read-only)", verdict)
        + "\n"
        + _block("라이브 실적 JSON (현재 단 진입 이후, read-only)", growth)
    )
    if anchored is not None:
        text += "\n" + _block(
            "앵커드 판정 JSON (깊은 OOS + 짧은 forward 지속성, read-only)",
            anchored,
        )
    return text


_CANARY_SIDECAR = (
    "# 라이브 캐너리 포트폴리오 — 최신 실행\n\n"
    "| 항목 | 값 |\n|------|-----|\n"
    "| armed (무장 여부) | false |\n"
    "| capital_usd | 500 |\n"
)

_CANARY_ARMED_SIDECAR = _CANARY_SIDECAR.replace(
    "armed (무장 여부) | false", "armed (무장 여부) | true"
)

_PRODUCTION_CANARY_PREFLIGHT_READY_SIDECAR = (
    "# 라이브 캐너리 포트폴리오 — 최신 실행 (가드형 실거래 채널)\n\n"
    "| 항목 | 값 |\n|------|-----|\n"
    "| run_id | 33353865976 |\n"
    "| timestamp_utc | 2026-08-31T03:12:45Z |\n"
    "| armed (무장 여부) | true |\n"
    "| capital_usd | 142 |\n"
    "| 첫 체결 전 최신 엣지 재검증 | success |\n"
    "| event | workflow_dispatch |\n"
    "| LIVE 스텝 | success (success=명령 종료 코드 0) |\n\n"
    "## 드라이런 미리보기 — 무장 시 거래할 내역 (주문 0건)\n"
    "```json\n"
    "(preview job 이 직전 sidecar에 발행함)\n"
    "```\n\n"
    "## 첫 체결 전 최신 엣지 재검증\n"
    "```json\n"
    "evidence_age_hours=0.75 canary_exit=0 profit_exit=0 "
    "proxy_parity_exit=0 fundability_exit=0\n"
    + json.dumps(
        {
            "allowed": True,
            "reasons": [],
            "state": "ENTRY_READY",
        },
        ensure_ascii=False,
    )
    + "\n```\n"
)

_PRODUCTION_CANARY_PREFLIGHT_MALFORMED_SIDECAR = (
    _PRODUCTION_CANARY_PREFLIGHT_READY_SIDECAR.replace(
        json.dumps(
            {
                "allowed": True,
                "reasons": [],
                "state": "ENTRY_READY",
            },
            ensure_ascii=False,
        ),
        "(entry revalidation JSON missing)",
    )
)

_MICRO_SIDECAR_OLD_FORMAT = (
    "# 마이크로 GTAA 라이브 캐너리 — 최신 실행\n\n"
    "| 항목 | 값 |\n|------|-----|\n"
    "| run_id | 27935469561 |\n"
    "| timestamp_utc | 2026-06-22T07:04:12Z |\n"
    "| armed | true |\n"
    "| capital_usd | 1000 |\n"
    "| blocked | false |\n"
    "| event | workflow_dispatch |\n"
    "| LIVE 스텝 | success (success=실주문 실행 / skipped=미실행) |\n\n"
    "## 라이브 전 손실 브레이커\n"
    "```json\n"
    '{"reason": "within loss limits", "tripped": false}\n'
    "```\n\n"
    "## 라이브 재조정 결과\n"
    "```json\n"
    '{"results": [{"state": "REJECTED_BY_BROKER"}, {"state": "REJECTED_BY_BROKER"}]}\n'
    "```\n"
)

_MICRO_SIDECAR_INTENT_LOSS = (
    "# 마이크로 GTAA 라이브 캐너리 — 최신 실행\n\n"
    "| 항목 | 값 |\n|------|-----|\n"
    "| run_id | 30287251205 |\n"
    "| timestamp_utc | 2026-07-28T16:14:45Z |\n"
    "| armed | true |\n"
    "| capital_usd | 1000 |\n"
    "| blocked | true |\n"
    "| event | workflow_dispatch |\n"
    "| LIVE 스텝 | skipped |\n\n"
    + _block(
        "라이브 전 전략 의도 게이트",
        {
            "schema_version": 1,
            "ok": False,
            "reason": "latest_intent_loss",
            "blocking_reasons": ["latest_intent_loss"],
            "latest_signal": "INTENT_LOSS",
        },
    )
    + _block(
        "라이브 전 손실 브레이커",
        {"reason": "within loss limits", "tripped": False},
    )
)

_MICRO_REQUEST_ARMED = """armed: true
capital_usd: 1000
requested_by: mason
stage: micro-gtaa-live-canary
run_seq: 2
warning_drawdown_pct: 3
hard_stop_drawdown_pct: 5
note: "운영자 2026-06-22 명시 승인"
"""

_MICRO_REQUEST_DISARMED = _MICRO_REQUEST_ARMED.replace("armed: true", "armed: false")

_LIVE_REQUEST_ARMED = """armed: true
capital_usd: 293
requested_by: spec-050-capital-ladder
stage: live-canary-portfolio
run_seq: 6
ladder_rung: 1
account_nav_usd: 1466.83000000
dd_budget_pct: 20.0
"""


def _recovery_sidecar(observed_at: str) -> str:
    return json.dumps(
        {
            "status": "CLEAR",
            "observed_at_utc": observed_at,
            "halt_present_after": False,
            "reconciliation_state": "OK",
            "evidence_quality": "VALID",
            "halt_cleared": False,
            "orders_submitted": 0,
            "reasons": [],
        }
    )


def _write(d: Path, key: str, text: str) -> None:
    (d / f"{key}.md").write_text(text, encoding="utf-8")


def test_probe_accumulating_text(tmp_path, capsys):
    _write(tmp_path, "edge-autoarm", _edge_sidecar())
    _write(tmp_path, "rebalance-live-canary", _CANARY_SIDECAR)
    rc = probe_main(["--sidecar-dir", str(tmp_path), "--now", "2026-06-13T08:00:00Z"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "ACCUMULATING_EDGE" in out
    assert "1/20" in out  # 관측 1/최소 20
    assert "돈 0 이동" in out


def test_probe_accumulating_json(tmp_path, capsys):
    _write(tmp_path, "edge-autoarm", _edge_sidecar())
    _write(tmp_path, "rebalance-live-canary", _CANARY_SIDECAR)
    rc = probe_main(
        ["--sidecar-dir", str(tmp_path), "--json", "--now", "2026-06-13T08:00:00Z"]
    )
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["stage"] == "ACCUMULATING_EDGE"
    assert out["current_rung"] == 0
    assert out["canary_armed"] is False
    assert out["account_nav_usd"] == "1518.21000000"
    assert out["eta"]["obs_remaining"] == 19
    # 다음 실행 ETA 실측용 prior 힌트가 실려야 한다.
    assert out["forward_n_obs"] == 1
    assert out["as_of_utc"] == "2026-06-13T08:00:00Z"


def test_probe_surfaces_anchored_no_edge_instead_of_false_accumulation(tmp_path, capsys):
    anchored = {
        "schema_version": "1.0",
        "method": "backtest_anchored",
        "verdict": "NO_EDGE",
        "reason": "OOS 구간 과반 실패",
        "oos_n_obs": 748,
        "forward_n_obs": 4,
        "oos_significance": "0.998745",
    }
    _write(tmp_path, "edge-autoarm", _edge_sidecar(n_obs=4, anchored=anchored))
    _write(tmp_path, "rebalance-live-canary", _CANARY_SIDECAR)

    rc = probe_main(
        ["--sidecar-dir", str(tmp_path), "--json", "--now", "2026-06-13T08:00:00Z"]
    )

    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["stage"] == "NO_EDGE_YET"
    assert out["eta"]["basis"] == "n/a"
    assert out["blocking_gate"] == "앵커드 OOS 실패: OOS 구간 과반 실패"
    gates = {gate["name"]: gate for gate in out["gates"]}
    assert gates["앵커드 표본외 판정"]["status"] == "FAIL"
    assert gates["짧은 전진 관측"]["current"] == "4/20"


def test_probe_measured_eta_from_prior_sidecar(tmp_path, capsys):
    # 직전 money-path 사이드카(결정 JSON 안에 forward_n_obs + as_of_utc 힌트).
    prior_hint = {"as_of_utc": "2026-06-09T08:00:00Z", "forward_n_obs": 1}
    prior = "# 첫-자본까지의 길\n\n" + _block("결정 JSON", prior_hint)
    # now 6/12(금), 관측 5 → 직전 6/9(화) 관측 1 → 3 거래일에 4 관측.
    _write(tmp_path, "edge-autoarm", _edge_sidecar(n_obs=5))
    _write(tmp_path, "rebalance-live-canary", _CANARY_SIDECAR)
    _write(tmp_path, "money-path", prior)
    rc = probe_main(
        ["--sidecar-dir", str(tmp_path), "--json", "--now", "2026-06-12T08:00:00Z"]
    )
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["eta"]["basis"] == "measured"
    assert out["eta"]["obs_remaining"] == 15


def test_probe_emits_legacy_hint_and_eta_fields(tmp_path, capsys):
    # forward 판정의 legacy/snapshot 이 ETA 와 prior 힌트(forward_legacy_excluded)로 실린다.
    _write(tmp_path, "edge-autoarm", _edge_sidecar(n_obs=1, legacy=4, snapshots=2))
    _write(tmp_path, "rebalance-live-canary", _CANARY_SIDECAR)
    rc = probe_main(
        ["--sidecar-dir", str(tmp_path), "--json", "--now", "2026-06-13T08:00:00Z"]
    )
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["forward_legacy_excluded"] == 4  # 다음 실행 비교용 prior 힌트
    assert out["eta"]["legacy_excluded"] == 4
    assert out["eta"]["snapshot_count"] == 2


def test_probe_churning_detected_from_prior_sidecar(tmp_path, capsys):
    # 직전 사이드카 제외 2 → 이번 4 로 늘어남 + 관측 정체 → 표본 흔들림(churning) 게이트
    # FAIL, end-to-end(드라이버가 직전 힌트를 읽어 비교).
    prior_hint = {
        "as_of_utc": "2026-06-11T08:00:00Z",
        "forward_n_obs": 1,
        "forward_legacy_excluded": 2,
    }
    prior = "# 첫-자본까지의 길\n\n" + _block("결정 JSON", prior_hint)
    _write(tmp_path, "edge-autoarm", _edge_sidecar(n_obs=1, legacy=4, snapshots=2))
    _write(tmp_path, "rebalance-live-canary", _CANARY_SIDECAR)
    _write(tmp_path, "money-path", prior)
    rc = probe_main(
        ["--sidecar-dir", str(tmp_path), "--json", "--now", "2026-06-13T08:00:00Z"]
    )
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["eta"]["sample_stability"] == "churning"
    gate = next(g for g in out["gates"] if g["name"] == "전진 표본 안정성(베이시스)")
    assert gate["status"] == "FAIL"


def test_probe_missing_all_sidecars_is_blocked(tmp_path, capsys):
    # 사이드카 전무 → ladder/verdict None → BLOCKED(안전), 종료코드 0(보고 전용).
    rc = probe_main(
        ["--sidecar-dir", str(tmp_path), "--json", "--now", "2026-06-13T08:00:00Z"]
    )
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["stage"] == "BLOCKED"


def test_probe_manifest():
    rc = probe_main(["--manifest"])
    assert rc == 0


def test_probe_manifest_lists_consumed_sidecars(capsys):
    probe_main(["--manifest"])
    out = capsys.readouterr().out
    assert "edge-autoarm\tautomation/edge-autoarm-last-run\tLAST_RUN.md" in out
    assert (
        "rebalance-micro-gtaa\tautomation/rebalance-micro-gtaa-last-run\tLAST_RUN.md"
        in out
    )
    assert (
        "live-profit-evidence\tautomation/live-profit-evidence-last-run\t"
        "profit_evidence.json" in out
    )
    assert "money-path\tautomation/money-path-last-run\tLAST_RUN.md" in out
    assert (
        "reconciliation-halt-recovery\t"
        "automation/reconciliation-halt-recovery-last-run\treport.json" in out
    )


def test_probe_surfaces_live_profit_evidence(tmp_path, capsys):
    _write(tmp_path, "edge-autoarm", _edge_sidecar())
    _write(tmp_path, "rebalance-live-canary", _CANARY_SIDECAR)
    _write(
        tmp_path,
        "live-profit-evidence",
        json.dumps(
            {
                "status": "FIRST_PROFIT_OBSERVED",
                "current_status": "FIRST_PROFIT_OBSERVED",
                "fills_count": 2,
                "total_pnl_usd": "0.42",
                "first_profit_observed": True,
                "first_profit_observed_at_utc": "2026-08-18T00:05:00Z",
            }
        ),
    )

    rc = probe_main(
        ["--sidecar-dir", str(tmp_path), "--json", "--now", "2026-08-18T00:06:00Z"]
    )

    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["live_profit_evidence"]["first_profit_observed"] is True
    assert out["live_profit_evidence"]["total_pnl_usd"] == "0.42"


def test_probe_prefers_armed_capital_ladder_live_path(tmp_path, capsys):
    _write(tmp_path, "edge-autoarm", _edge_sidecar())
    _write(tmp_path, "rebalance-live-canary", _CANARY_ARMED_SIDECAR)
    _write(
        tmp_path,
        "reconciliation-halt-recovery",
        _recovery_sidecar("2026-08-16T02:00:00Z"),
    )
    live_request = tmp_path / "rebalance-live.request"
    live_request.write_text(_LIVE_REQUEST_ARMED, encoding="utf-8")
    micro_request = tmp_path / "rebalance-micro-gtaa.request"
    micro_request.write_text(_MICRO_REQUEST_DISARMED, encoding="utf-8")

    rc = probe_main(
        [
            "--sidecar-dir",
            str(tmp_path),
            "--json",
            "--now",
            "2026-08-16T02:00:00Z",
            "--live-request",
            str(live_request),
            "--micro-request",
            str(micro_request),
        ]
    )

    assert rc == 0
    state = json.loads(capsys.readouterr().out)["live_money_state"]
    assert state["status"] == "REAL_ORDER_PATH_ARMED"
    assert state["can_submit_real_orders"] is True
    assert state["path"] == "capital-ladder-live-canary"
    assert state["capital_usd"] == 293
    assert state["next_scheduled_live_utc"] == "2026-08-17T14:17:00Z"


def test_probe_maps_production_first_entry_revalidation_to_preflight(tmp_path, capsys):
    _write(tmp_path, "edge-autoarm", _edge_sidecar())
    _write(
        tmp_path,
        "rebalance-live-canary",
        _PRODUCTION_CANARY_PREFLIGHT_READY_SIDECAR,
    )
    _write(
        tmp_path,
        "reconciliation-halt-recovery",
        _recovery_sidecar("2026-08-31T03:13:00Z"),
    )
    live_request = tmp_path / "rebalance-live.request"
    live_request.write_text(_LIVE_REQUEST_ARMED, encoding="utf-8")

    rc = probe_main(
        [
            "--sidecar-dir",
            str(tmp_path),
            "--json",
            "--now",
            "2026-08-31T04:00:00Z",
            "--live-request",
            str(live_request),
            "--micro-request",
            "",
        ]
    )

    assert rc == 0
    run = json.loads(capsys.readouterr().out)["live_money_state"]["last_run"]
    assert run["run_id"] == "33353865976"
    assert run["preflight_ok"] is True
    assert run["preflight_reason"] == "ENTRY_READY"


def test_probe_does_not_trust_success_row_without_revalidation_json(tmp_path, capsys):
    _write(tmp_path, "edge-autoarm", _edge_sidecar())
    _write(
        tmp_path,
        "rebalance-live-canary",
        _PRODUCTION_CANARY_PREFLIGHT_MALFORMED_SIDECAR,
    )
    _write(
        tmp_path,
        "reconciliation-halt-recovery",
        _recovery_sidecar("2026-08-31T03:13:00Z"),
    )
    live_request = tmp_path / "rebalance-live.request"
    live_request.write_text(_LIVE_REQUEST_ARMED, encoding="utf-8")

    rc = probe_main(
        [
            "--sidecar-dir",
            str(tmp_path),
            "--json",
            "--now",
            "2026-08-31T04:00:00Z",
            "--live-request",
            str(live_request),
            "--micro-request",
            "",
        ]
    )

    assert rc == 0
    run = json.loads(capsys.readouterr().out)["live_money_state"]["last_run"]
    assert run["preflight_ok"] is None
    assert run["preflight_reason"] == "preflight evidence absent"


def test_probe_micro_armed_state_is_top_level_json(tmp_path, capsys):
    req = tmp_path / "micro.request"
    req.write_text(_MICRO_REQUEST_ARMED, encoding="utf-8")
    _write(tmp_path, "edge-autoarm", _edge_sidecar())
    _write(tmp_path, "rebalance-live-canary", _CANARY_SIDECAR)
    _write(tmp_path, "rebalance-micro-gtaa", _MICRO_SIDECAR_OLD_FORMAT)
    _write(
        tmp_path,
        "reconciliation-halt-recovery",
        _recovery_sidecar("2026-06-22T12:55:00Z"),
    )
    rc = probe_main(
        [
            "--sidecar-dir",
            str(tmp_path),
            "--micro-request",
            str(req),
            "--live-request",
            "",
            "--json",
            "--now",
            "2026-06-22T12:55:00Z",
        ]
    )
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    live = out["live_money_state"]
    assert live["status"] == "REAL_ORDER_PATH_ARMED"
    assert live["can_submit_real_orders"] is True
    assert live["capital_usd"] == 1000
    assert live["next_scheduled_live_utc"] == "2026-06-22T15:00:00Z"
    assert live["last_run"]["broker_rejected_count"] == 2
    assert live["last_run"]["accepted_or_filled_count"] == 0
    assert live["last_run"]["preflight_reason"] == "preflight evidence absent"


def test_probe_micro_intent_loss_blocks_live_money_state(tmp_path, capsys):
    req = tmp_path / "micro.request"
    req.write_text(_MICRO_REQUEST_ARMED, encoding="utf-8")
    _write(tmp_path, "edge-autoarm", _edge_sidecar())
    _write(tmp_path, "rebalance-live-canary", _CANARY_SIDECAR)
    _write(tmp_path, "rebalance-micro-gtaa", _MICRO_SIDECAR_INTENT_LOSS)
    _write(
        tmp_path,
        "reconciliation-halt-recovery",
        _recovery_sidecar("2026-07-28T16:20:00Z"),
    )
    rc = probe_main(
        [
            "--sidecar-dir",
            str(tmp_path),
            "--micro-request",
            str(req),
            "--live-request",
            "",
            "--json",
            "--now",
            "2026-07-28T16:20:00Z",
        ]
    )
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    live = out["live_money_state"]
    assert live["status"] == "BLOCKED"
    assert live["can_submit_real_orders"] is False
    assert live["next_scheduled_live_utc"] is None
    assert "latest_intent_loss" in live["detail"]
    assert live["last_run"]["intent_gate_ok"] is False
    assert live["last_run"]["intent_gate_reason"] == "latest_intent_loss"


def test_probe_micro_disarmed_state_is_preview_only_text(tmp_path, capsys):
    req = tmp_path / "micro.request"
    req.write_text(_MICRO_REQUEST_DISARMED, encoding="utf-8")
    _write(tmp_path, "edge-autoarm", _edge_sidecar())
    _write(tmp_path, "rebalance-live-canary", _CANARY_SIDECAR)
    _write(
        tmp_path,
        "reconciliation-halt-recovery",
        _recovery_sidecar("2026-06-22T12:55:00Z"),
    )
    rc = probe_main(
        [
            "--sidecar-dir",
            str(tmp_path),
            "--micro-request",
            str(req),
            "--live-request",
            "",
            "--now",
            "2026-06-22T12:55:00Z",
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "실제 돈 최상위 상태" in out
    assert "미리보기 전용" in out
    assert "## 기존 자본 사다리 상태" in out
    assert out.index("실제 돈 최상위 상태") < out.index("## 기존 자본 사다리 상태")


# ── 전략 지문 정합(compute_fingerprint_status) — 사다리 게이트와 동일 비교 ──

_PF_MINI = """
[portfolio]
id = "t"
universe = {universe}
weights = {{ momentum = "1.0" }}
weight_scheme = "equal"
top_n = {top_n}
"""


def _write_pf(p: Path, universe: str, top_n: int = 2) -> Path:
    p.write_text(_PF_MINI.format(universe=universe, top_n=top_n), encoding="utf-8")
    return p


def test_fingerprint_status_match(tmp_path):
    a = _write_pf(tmp_path / "a.toml", '["SPY", "IEF"]')
    b = _write_pf(tmp_path / "b.toml", '["SPY", "IEF"]')
    out = _probe.compute_fingerprint_status(a, b)
    assert out["match"] is True
    assert out["diverged"] == []


def test_fingerprint_status_mismatch_lists_universe(tmp_path):
    a = _write_pf(tmp_path / "a.toml", '["SPY", "QQQ"]')
    b = _write_pf(tmp_path / "b.toml", '["SPY", "IEF"]')
    out = _probe.compute_fingerprint_status(a, b)
    assert out["match"] is False
    assert "universe" in out["diverged"]


def test_fingerprint_status_mismatch_top_n(tmp_path):
    a = _write_pf(tmp_path / "a.toml", '["SPY", "IEF"]', top_n=1)
    b = _write_pf(tmp_path / "b.toml", '["SPY", "IEF"]', top_n=2)
    out = _probe.compute_fingerprint_status(a, b)
    assert out["match"] is False
    assert "top_n" in out["diverged"]


def test_fingerprint_status_missing_file_is_none(tmp_path):
    b = _write_pf(tmp_path / "b.toml", '["SPY", "IEF"]')
    out = _probe.compute_fingerprint_status(tmp_path / "nope.toml", b)
    assert out["match"] is None
    assert out["live_path"].endswith("nope.toml")


def test_fingerprint_status_bad_toml_is_none(tmp_path):
    bad = tmp_path / "bad.toml"
    bad.write_text("this is not valid toml {{{", encoding="utf-8")
    b = _write_pf(tmp_path / "b.toml", '["SPY", "IEF"]')
    out = _probe.compute_fingerprint_status(bad, b)
    assert out["match"] is None


def test_fingerprint_status_missing_portfolio_section_is_none(tmp_path):
    nopf = tmp_path / "nopf.toml"
    nopf.write_text('[caps]\nmax = "1"\n', encoding="utf-8")
    b = _write_pf(tmp_path / "b.toml", '["SPY", "IEF"]')
    out = _probe.compute_fingerprint_status(nopf, b)
    assert out["match"] is None


def test_probe_emits_fingerprint_gate_when_configs_given(tmp_path, capsys):
    # 실제 배포/검증 설정을 넘기면 전략 지문 게이트가 보고 JSON 의 gates 에 나온다.
    _write(tmp_path, "edge-autoarm", _edge_sidecar(n_obs=1))
    a = _write_pf(tmp_path / "live.toml", '["SPY", "IEF"]')
    b = _write_pf(tmp_path / "val.toml", '["SPY", "IEF"]')
    rc = probe_main(
        [
            "--sidecar-dir", str(tmp_path), "--json", "--now", "2026-06-13T08:00:00Z",
            "--live-portfolio", str(a), "--validated-portfolio", str(b),
        ]
    )
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    gate = next(g for g in out["gates"] if g["name"] == "전략 지문 정합(검증=배포)")
    assert gate["status"] == "PASS"
