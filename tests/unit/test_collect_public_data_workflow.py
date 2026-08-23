"""공개 데이터 수집 워크플로 불변식 (계획 ④ — 연구 전용 격리, 2026-06-11).

채널의 안전 계약을 CI 에 못박는다:
  1. 돈 경로 무접촉 — 워크플로에 KIS/Vultr 시크릿·SSH 가 없어야 한다.
  2. 격리 — 거래 워크플로가 검증 전 원시 public-data 산출물을 직접 읽지
     않아야 한다(거시 전략은 FACTORY_EDGE 사이드카만 주문 전에 읽는다).
  3. 설정 정합 — 교차 검증 짝이 실제 수집 목록에 있어야 한다. FRED 그래프
     CSV 는 DGS2/DGS10 금리만 연구 수집에 허용하고, FRED 공식 API 키 경로와
     Stooq 가격 CSV 는 탐침/후속 선택지로만 둔다.

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
    refs = {part.split("}")[0].strip() for part in text.split("secrets.")[1:]}
    assert refs == {"GITHUB_TOKEN"}, refs


def test_trading_workflows_do_not_consume_public_data() -> None:
    """거래 워크플로는 검증 전 원시 public-data 채널을 직접 읽지 않는다."""
    for wf in _TRADING_WORKFLOWS:
        assert "public-data" not in wf.read_text(encoding="utf-8"), wf.name


def test_module_cannot_write_live_price_bars() -> None:
    """연구 모듈이 라이브 DB/price_bars 적재 경로를 임포트하지 않는다."""
    text = _MODULE.read_text(encoding="utf-8")
    assert "insert_bar" not in text
    assert "auto_invest.db" not in text
    assert "from auto_invest.persistence" not in text
    assert "from auto_invest.broker" not in text


def test_config_parses_and_cross_checks_reference_collected_ids() -> None:
    """설정 정합 — 모든 교차 검증 짝이 실제 수집되는 레지스트리 키를 가리킨다.

    4차(2026-06-11, 운영자 선택) 이후 수집은 공식 키리스 조합(재무부·Cboe·
    BLS·DBnomics)에 FRED 그래프 CSV 국채 만기 5종과 CPIAUCNS/SAHMREALTIME을 더한다.
    Stooq 가격 CSV 와 FRED 공식 API 키 경로는 탐침/후속 선택지로만 둔다.
    가격 이력 확장은 보류 — 가격 소스는 KIS 백필 유지(ARM F 유니버스 정합
    단언이 사라진 이유).
    """
    cfg = tomllib.loads(_CONFIG.read_text(encoding="utf-8"))
    # 차단된 가격 소스가 수집 목록에 되살아나지 않게 — 탐침([probes])으로만 추적.
    assert "stooq" not in cfg
    assert cfg["fred"]["series"] == [
        "DGS3MO",
        "DGS2",
        "DGS5",
        "DGS10",
        "DGS30",
        "CPIAUCNS",
        "SAHMREALTIME",
    ]
    assert cfg["fred"]["user_agent"] == "httpx-default"
    # 수집 시 레지스트리에 올라갈 "provider:id" 키를 설정에서 재구성한다.
    collected: set[str] = set()
    tre = cfg.get("treasury", {})
    for item_id in tre.get("maturities", {}).values():
        collected.add(f"treasury:{item_id}")
    if "spread" in tre:
        collected.add(f"treasury:{tre['spread']['id']}")
        # 스프레드 다리가 수집 만기에 있어야 계산 가능.
        for leg in ("long", "short"):
            assert tre["spread"][leg] in tre["maturities"], leg
    if cfg.get("cboe", {}).get("vix"):
        collected.add("cboe:VIX")
    for sid in cfg.get("bls", {}).get("series", []):
        collected.add(f"bls:{sid}")
    for sid in cfg.get("fred", {}).get("series", []):
        collected.add(f"fred:{sid}")
    for code in cfg.get("dbnomics", {}).get("series", []):
        collected.add(f"dbnomics:{code}")
    joined_cfg = "\n".join(str(value) for key, value in cfg.items() if key != "probes")
    assert "api.stlouisfed.org/fred/series/observations" not in joined_cfg
    assert len(collected) >= 4, "공식 키리스 조합이 통째로 사라짐"
    checks = cfg.get("cross_checks", [])
    assert len(checks) >= 1, "교차 검증 0개 — 단일 전송 경로 오염을 못 잡는다"
    for cc in checks:
        assert cc["a"] in collected, f"교차 검증 입력 {cc['a']} 이 수집 목록에 없음"
        assert cc["b"] in collected, f"교차 검증 입력 {cc['b']} 이 수집 목록에 없음"


def test_treasury_yields_have_two_source_cross_check() -> None:
    """금리 두-기관 대조 — 재무부 직접 수집의 각 만기는 연준 H.15(DBnomics 미러)
    수준 대조 짝을 가져야 한다. 레짐 분석(금리차)의 핵심 입력이 단일 전송 경로에
    매달리지 않게 하는 불변식 (2026-06-12, 탐침 증거 수집 완료 후 채택)."""
    cfg = tomllib.loads(_CONFIG.read_text(encoding="utf-8"))
    checks = cfg.get("cross_checks", [])
    for item_id in cfg["treasury"]["maturities"].values():
        paired = [
            cc
            for cc in checks
            if cc["a"] == f"treasury:{item_id}" and cc["b"].startswith("dbnomics:FED/H15/")
        ]
        assert paired, f"treasury:{item_id} 에 연준 H.15 대조 짝이 없음"
        for cc in paired:
            assert cc["kind"] == "levels"


def test_fred_yields_have_treasury_cross_check() -> None:
    """FRED DGS 금리 수집은 단독 발행이 아니라 재무부 직접 수집과 수준 대조된다."""
    cfg = tomllib.loads(_CONFIG.read_text(encoding="utf-8"))
    checks = cfg.get("cross_checks", [])
    expected_pairs = {
        "DGS2": "treasury:UST2Y",
        "DGS10": "treasury:UST10Y",
    }
    for series_id in ("DGS2", "DGS10"):
        paired = [
            cc
            for cc in checks
            if cc["a"] == expected_pairs[series_id] and cc["b"] == f"fred:{series_id}"
        ]
        assert paired, f"fred:{series_id} 에 재무부 대조 짝이 없음"
        for cc in paired:
            assert cc["kind"] == "levels"
            assert cc["min_agree_pct"] == "99.5"


def test_deep_macro_series_have_individual_validation_and_cpi_cross_check() -> None:
    cfg = tomllib.loads(_CONFIG.read_text(encoding="utf-8"))
    settings = cfg["fred"]["series_settings"]
    assert settings["CPIAUCNS"]["min_rows"] >= 1200
    assert settings["SAHMREALTIME"]["min_rows"] >= 700
    assert any(
        cc["a"] == "fred:CPIAUCNS" and cc["b"] == "dbnomics:BLS/cu/CUUR0000SA0"
        for cc in cfg["cross_checks"]
    )


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
