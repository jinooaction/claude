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


def _edge_sidecar(n_obs: int = 1) -> str:
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
    growth = {
        "schema_version": "1.0",
        "mode": "live",
        "snapshot_count": 3,
        "current_nav_usd": "500.0",
        "period_days": "1.25",
    }
    return (
        "# 자본 사다리 게이트 — 최신 실행\n\n"
        "| 항목 | 값 |\n|------|-----|\n"
        "| timestamp_utc | 2026-06-13T01:53:50Z |\n\n"
        + _block("결정 JSON", ladder)
        + "\n"
        + _block("forward 판정 JSON (검증된 앙상블, read-only)", verdict)
        + "\n"
        + _block("라이브 실적 JSON (현재 단 진입 이후, read-only)", growth)
    )


_CANARY_SIDECAR = (
    "# 라이브 캐너리 포트폴리오 — 최신 실행\n\n"
    "| 항목 | 값 |\n|------|-----|\n"
    "| armed (무장 여부) | false |\n"
    "| capital_usd | 500 |\n"
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
    assert "money-path\tautomation/money-path-last-run\tLAST_RUN.md" in out
