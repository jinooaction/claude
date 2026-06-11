"""공개 데이터 수집 워크플로 불변식 (계획 ④ — 연구 전용 격리, 2026-06-11).

채널의 안전 계약을 CI 에 못박는다:
  1. 돈 경로 무접촉 — 워크플로에 KIS/Vultr 시크릿·SSH 가 없어야 한다.
  2. 격리 — 라이브/forward 거래 워크플로와 모듈이 public-data 산출물을
     읽지 않아야 한다(라이브 매매 신호는 KIS 데이터만).
  3. 설정 정합 — 교차 검증 짝이 실제 수집 목록에 있어야 한다.

워크플로는 셸 조립이 많아 YAML 파싱 대신 텍스트 불변식을 검사한다
(test_workflow_backfill_depth.py 와 동일 접근).
"""

from __future__ import annotations

import tomllib
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_WF = _REPO_ROOT / ".github" / "workflows" / "collect-public-data.yml"
_CONFIG = _REPO_ROOT / "deploy" / "public-data.toml"
_MODULE = _REPO_ROOT / "src" / "auto_invest" / "market_data" / "public_data.py"

_TRADING_WORKFLOWS = [
    _REPO_ROOT / ".github" / "workflows" / "rebalance-live-canary.yml",
    _REPO_ROOT / ".github" / "workflows" / "rebalance-paper-forward.yml",
    _REPO_ROOT / ".github" / "workflows" / "go-live-canary.yml",
    _REPO_ROOT / ".github" / "workflows" / "forward-edge-autoarm.yml",
]


def _wf_text() -> str:
    return _WF.read_text(encoding="utf-8")


def test_workflow_exists_with_schedule_dispatch_and_sidecar() -> None:
    text = _wf_text()
    assert "schedule:" in text and "cron:" in text
    assert "workflow_dispatch:" in text
    assert "automation/public-data" in text
    assert "collect-public-data" in text
    assert "--config deploy/public-data.toml" in text


def test_workflow_touches_no_money_path_secrets() -> None:
    """돈 경로 무접촉 — 시크릿은 사이드카 push 용 GITHUB_TOKEN 하나뿐."""
    text = _wf_text()
    assert "VULTR_SSH" not in text
    assert "KIS_" not in text
    assert "ssh " not in text and "ssh -" not in text
    # 시크릿 참조는 GITHUB_TOKEN 단 하나.
    refs = {
        part.split("}")[0].strip()
        for part in text.split("secrets.")[1:]
    }
    assert refs == {"GITHUB_TOKEN"}, refs


def test_trading_workflows_do_not_consume_public_data() -> None:
    """라이브 매매 신호는 KIS 데이터만 — 거래 워크플로가 이 채널을 읽지 않는다."""
    for wf in _TRADING_WORKFLOWS:
        assert "public-data" not in wf.read_text(encoding="utf-8"), wf.name


def test_module_cannot_write_live_price_bars() -> None:
    """연구 모듈이 라이브 DB/price_bars 적재 경로를 임포트하지 않는다."""
    text = _MODULE.read_text(encoding="utf-8")
    assert "insert_bar" not in text
    assert "auto_invest.db" not in text
    assert "from auto_invest.persistence" not in text
    assert "from auto_invest.broker" not in text


def test_config_parses_and_cross_check_pair_is_collected() -> None:
    cfg = tomllib.loads(_CONFIG.read_text(encoding="utf-8"))
    symbols = cfg["stooq"]["symbols"]
    series = cfg["fred"]["series"]
    assert len(symbols) >= 1 and len(series) >= 1
    cc = cfg["cross_check"]
    assert cc["stooq_symbol"] in symbols
    assert cc["fred_series"] in series
    # ARM F(유니버스 확대 forward 트랙)의 11개 슬리브가 전부 연구 대상에 있어야
    # 검증 트랙과 연구 데이터가 같은 우주를 본다(검증=연구 정합).
    wide = tomllib.loads(
        (_REPO_ROOT / "deploy" / "global-trend-wide-portfolio.toml").read_text(
            encoding="utf-8"
        )
    )
    for sleeve in wide["portfolio"]["universe"]:
        assert sleeve in symbols, f"ARM F 슬리브 {sleeve} 가 public-data 수집 목록에 없음"


def test_collect_step_has_own_timeout_below_job_limit() -> None:
    """수집이 늘어져도 발행 스텝이 항상 실행되게 — 첫 실측(2026-06-11)에서
    FRED 타르핏이 작업 제한을 잡아먹어 collect_exit 가 미기록됐던 회귀 방지."""
    text = _wf_text()
    assert "timeout-minutes: 12" in text
    assert "timeout-minutes: 15" in text  # 작업 제한이 스텝 제한보다 크다


def test_config_has_time_budget_and_probes() -> None:
    cfg = tomllib.loads(_CONFIG.read_text(encoding="utf-8"))
    coll = cfg["collection"]
    assert float(coll["time_budget_seconds"]) <= 600  # 스텝 제한(12분) 아래
    assert float(coll["request_timeout_seconds"]) <= 30
    assert len(cfg["probes"]["urls"]) >= 1


def test_workflow_push_paths_cover_channel_files() -> None:
    """채널 파일이 바뀐 머지에서 즉시 실전 검증(같은 날 검증 패턴)."""
    text = _wf_text()
    for path in (
        "src/auto_invest/market_data/public_data.py",
        "deploy/public-data.toml",
        ".github/workflows/collect-public-data.yml",
    ):
        assert path in text
