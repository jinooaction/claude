"""거시 레짐 보고서 (계획 ④ 후속) — 지표·합성·fail-soft·격리 불변식.

네트워크 0, 라이브 DB 0 — 입력은 채널 표준 CSV 텍스트뿐.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from auto_invest.market_data.macro_regime import (
    CPI_CSV,
    SPREAD_CSV,
    UNEMPLOYMENT_CSV,
    VIX_CSV,
    build_macro_regime_report,
    build_point_in_time_snapshots,
    compose_overall,
    inflation_state,
    load_series_csv,
    sahm_rule_state,
    validate_live_macro_evidence,
    vix_state,
    yield_curve_state,
)

AS_OF = date(2026, 6, 12)


def _series_csv(rows: list[tuple[str, str]]) -> str:
    return "date,value\n" + "\n".join(f"{d},{v}" for d, v in rows)


def _points(values: list[str], *, start_month: tuple[int, int] = (2024, 1)) -> list:
    """월간 시계열 생성 (YYYY-MM-01)."""
    y, m = start_month
    out = []
    for v in values:
        out.append((f"{y:04d}-{m:02d}-01", Decimal(v) if v else None))
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


def _daily_points(start: date, count: int, value: str) -> list[tuple[str, Decimal]]:
    return [((start + timedelta(days=index)).isoformat(), Decimal(value)) for index in range(count)]


def test_point_in_time_snapshot_uses_lagged_monthly_and_prior_daily_values() -> None:
    target = date(2020, 8, 1)
    dgs2 = _daily_points(date(2020, 4, 1), 123, "1.0")
    dgs10 = _daily_points(date(2020, 4, 1), 123, "1.5")
    vix = _daily_points(date(2020, 4, 1), 123, "20")
    dgs2[-1] = (target.isoformat(), Decimal("9"))
    dgs10[-1] = (target.isoformat(), Decimal("1"))
    vix[-1] = (target.isoformat(), Decimal("99"))
    cpi = _points([str(100 + index) for index in range(36)], start_month=(2017, 7))
    sahm = _points([str(Decimal(index) / 100) for index in range(36)], start_month=(2017, 7))

    snapshot = build_point_in_time_snapshots(
        [target.isoformat()],
        dgs2=dgs2,
        dgs10=dgs10,
        cpi=cpi,
        sahm_realtime=sahm,
        vix=vix,
    )[0]

    assert snapshot.yield_spread_10y2y == Decimal("0.5")
    assert snapshot.vix_close == Decimal("20")
    assert snapshot.cpi_available_date is not None
    assert snapshot.cpi_available_date <= target.isoformat()
    assert snapshot.sahm_available_date is not None
    assert snapshot.complete is True and snapshot.fresh is True


def test_point_in_time_snapshot_fails_closed_on_cross_check_or_staleness() -> None:
    target = date(2020, 8, 1)
    daily_end = date(2020, 7, 1)
    dgs2 = _daily_points(date(2020, 3, 1), (daily_end - date(2020, 3, 1)).days + 1, "1")
    dgs10 = _daily_points(date(2020, 3, 1), len(dgs2), "1.5")
    vix = _daily_points(date(2020, 3, 1), len(dgs2), "20")
    monthly = _points([str(100 + index) for index in range(36)], start_month=(2017, 7))
    sahm = _points(["0.2"] * 36, start_month=(2017, 7))

    snapshot = build_point_in_time_snapshots(
        [target.isoformat()],
        dgs2=dgs2,
        dgs10=dgs10,
        cpi=monthly,
        sahm_realtime=sahm,
        vix=vix,
        cross_check_status="FAIL",
    )[0]

    assert snapshot.complete is True
    assert snapshot.fresh is False
    assert snapshot.source_freshness_days["yield_curve"] > 7


def test_live_macro_evidence_requires_exact_winner_identity_and_freshness() -> None:
    now = datetime(2026, 8, 23, tzinfo=UTC)
    payload = {
        "timestamp_utc": "2026-08-23T00:00:00Z",
        "decision": {
            "verdict": "FACTORY_EDGE",
            "research_canary_eligible": True,
            "selected_candidate_id": "macro-1",
            "selected_strategy_fingerprint": "sha256:abc",
        },
        "live_macro_evidence": {
            "candidate_id": "macro-1",
            "strategy_fingerprint": "sha256:abc",
            "fresh": True,
            "complete": True,
            "cross_checked": True,
            "latest_snapshot": {
                "as_of_date": "2026-08-23",
                "complete": True,
                "fresh": True,
            },
        },
    }
    snapshot = validate_live_macro_evidence(
        payload,
        candidate_id="macro-1",
        strategy_fingerprint="sha256:abc",
        now=now,
    )
    assert snapshot["as_of_date"] == "2026-08-23"
    payload["decision"]["selected_strategy_fingerprint"] = "sha256:different"
    with pytest.raises(ValueError, match="fingerprint"):
        validate_live_macro_evidence(
            payload,
            candidate_id="macro-1",
            strategy_fingerprint="sha256:abc",
            now=now,
        )


# ---------- CSV 로더 ----------


def test_load_series_csv_preserves_missing_and_sorts() -> None:
    pts = load_series_csv("date,value\n2026-06-02,1.5\n2026-06-01,\n")
    assert pts == [("2026-06-01", None), ("2026-06-02", Decimal("1.5"))]
    with pytest.raises(ValueError, match="헤더"):
        load_series_csv("a,b\n1,2\n")
    with pytest.raises(ValueError, match="숫자"):
        load_series_csv("date,value\n2026-06-01,abc\n")


# ---------- 금리 곡선 ----------


def test_yield_curve_states() -> None:
    inv = yield_curve_state([("2026-06-10", Decimal("-0.3"))])
    assert inv["state"] == "INVERTED" and inv["stress"] is True
    flat = yield_curve_state([("2026-06-10", Decimal("0.4"))])
    assert flat["state"] == "FLAT" and flat["stress"] is False
    norm = yield_curve_state([("2026-06-10", Decimal("0.8"))])
    assert norm["state"] == "NORMAL"
    assert yield_curve_state([])["status"] == "UNAVAILABLE"


def test_yield_curve_counts_inverted_days_in_window() -> None:
    pts = [(f"2026-01-{i:02d}", Decimal("-0.1")) for i in range(1, 11)]
    pts += [(f"2026-02-{i:02d}", Decimal("0.6")) for i in range(1, 6)]
    out = yield_curve_state(pts)
    assert out["inverted_days_252"] == 10 and out["state"] == "NORMAL"


# ---------- VIX ----------


def test_vix_bands_and_percentile() -> None:
    base = [(f"2026-01-{i:02d}", Decimal("12")) for i in range(1, 10)]
    calm = vix_state(base + [("2026-06-11", Decimal("14.9"))])
    assert calm["state"] == "CALM" and calm["stress"] is False
    crisis = vix_state(base + [("2026-06-11", Decimal("45"))])
    assert crisis["state"] == "CRISIS" and crisis["stress"] is True
    assert crisis["history_percentile"] == "100.0"  # 이력 최고치
    elevated = vix_state(base + [("2026-06-11", Decimal("30"))])
    assert elevated["state"] == "ELEVATED" and elevated["stress"] is True


# ---------- 물가 (CPI 전년동월비) ----------


def test_inflation_yoy_exact_and_bands() -> None:
    # 2025-06 = 300 → 2026-06 = 309 → YoY 3.00% (HIGH 경계)
    pts = _points(["300"] + [""] * 11 + ["309"], start_month=(2025, 6))
    out = inflation_state(pts)
    assert out["state"] == "HIGH" and out["yoy_pct"] == "3.00" and out["stress"] is True
    # 2% 미만 LOW, 음수 DEFLATION
    low = inflation_state(_points(["300"] + [""] * 11 + ["304.5"], start_month=(2025, 6)))
    assert low["state"] == "LOW" and low["stress"] is False
    defl = inflation_state(_points(["300"] + [""] * 11 + ["297"], start_month=(2025, 6)))
    assert defl["state"] == "DEFLATION" and defl["stress"] is True


def test_inflation_unavailable_when_base_month_missing() -> None:
    # 12개월 전 달이 결측("-" 미발표) → 정직하게 UNAVAILABLE
    pts = _points([""] + ["301"] * 11 + ["309"], start_month=(2025, 6))
    out = inflation_state(pts)
    assert out["status"] == "UNAVAILABLE" and "12개월 전" in out["reason"]


# ---------- 고용 (삼 룰) ----------


def test_sahm_rule_quiet_and_triggered() -> None:
    quiet = sahm_rule_state(_points(["4.0"] * 16))
    assert quiet["state"] == "QUIET" and quiet["sahm_value_pp"] == "0.00"
    # 마지막 3개월 실업률 급등 → 3개월 이동평균이 최솟값보다 0.5%p 이상 위
    rising = _points(["4.0"] * 13 + ["4.6", "4.8", "5.0"])
    out = sahm_rule_state(rising)
    assert out["state"] == "TRIGGERED" and out["stress"] is True
    assert Decimal(out["sahm_value_pp"]) >= Decimal("0.5")


def test_sahm_rule_insufficient_observations() -> None:
    out = sahm_rule_state(_points(["4.0"] * 14))
    assert out["status"] == "UNAVAILABLE" and "15개" in out["reason"]


# ---------- 합성 ----------


def _ok(stress: bool) -> dict:
    return {"status": "OK", "stress": stress}


def test_compose_overall_labels() -> None:
    assert compose_overall({"a": _ok(False), "b": _ok(False)})["label"] == "RISK_ON"
    assert compose_overall({"a": _ok(True), "b": _ok(False)})["label"] == "CAUTION"
    assert compose_overall({"a": _ok(True), "b": _ok(True)})["label"] == "RISK_OFF"
    # 계산 가능 지표 < 2 → 깃발 0개를 안전으로 오독하지 않는다
    out = compose_overall({"a": _ok(False), "b": {"status": "UNAVAILABLE"}})
    assert out["label"] == "INSUFFICIENT" and out["available_indicators"] == 1


# ---------- 보고서 생성 (fail-soft) ----------


def _write(data_dir: Path, rel: str, text: str) -> None:
    p = data_dir / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def test_build_report_full_inputs(tmp_path: Path) -> None:
    _write(tmp_path, SPREAD_CSV, _series_csv([("2026-06-11", "-0.2")]))
    _write(tmp_path, VIX_CSV, _series_csv([("2026-06-11", "18")]))
    cpi = _points(["300"] + [""] * 11 + ["307.5"], start_month=(2025, 6))
    _write(tmp_path, CPI_CSV, _series_csv([(d, str(v) if v else "") for d, v in cpi]))
    une = _points(["4.0"] * 16)
    _write(tmp_path, UNEMPLOYMENT_CSV, _series_csv([(d, str(v)) for d, v in une]))

    report = build_macro_regime_report(tmp_path, as_of=AS_OF)
    assert report["schema_version"] == "1.0" and report["as_of"] == "2026-06-12"
    ind = report["indicators"]
    assert ind["yield_curve"]["state"] == "INVERTED"
    assert ind["vix"]["state"] == "NORMAL"
    assert ind["inflation"]["state"] == "MODERATE"  # 2.50%
    assert ind["sahm"]["state"] == "QUIET"
    # 역전 깃발 1개 → CAUTION
    assert report["overall"]["label"] == "CAUTION"
    assert report["overall"]["stress_flags"] == ["yield_curve"]


def test_build_report_failsoft_missing_files(tmp_path: Path) -> None:
    _write(tmp_path, SPREAD_CSV, _series_csv([("2026-06-11", "0.9")]))
    _write(tmp_path, VIX_CSV, _series_csv([("2026-06-11", "13")]))
    report = build_macro_regime_report(tmp_path, as_of=AS_OF)
    assert report["indicators"]["inflation"]["status"] == "UNAVAILABLE"
    assert report["indicators"]["sahm"]["status"] == "UNAVAILABLE"
    assert report["overall"]["label"] == "RISK_ON"  # 가용 2개, 깃발 0개
    assert report["overall"]["available_indicators"] == 2


def test_build_report_empty_dir_is_insufficient(tmp_path: Path) -> None:
    report = build_macro_regime_report(tmp_path, as_of=AS_OF)
    assert report["overall"]["label"] == "INSUFFICIENT"
    assert report["overall"]["available_indicators"] == 0


# ---------- 격리·배선 불변식 ----------

_REPO_ROOT = Path(__file__).resolve().parents[2]


def test_module_is_research_only_no_live_imports() -> None:
    """라이브 DB/주문 경로 무접촉 — public_data.py 와 같은 격리 계약."""
    text = (_REPO_ROOT / "src" / "auto_invest" / "market_data" / "macro_regime.py").read_text(
        encoding="utf-8"
    )
    for forbidden in (
        "insert_bar",
        "auto_invest.db",
        "from auto_invest.persistence",
        "from auto_invest.broker",
        "from auto_invest.strategy",  # 라이브 가격 레짐과 섞이지 않는다
    ):
        assert forbidden not in text, forbidden


def test_live_trading_paths_do_not_import_macro_regime() -> None:
    """역방향 격리 — 라이브 경로(strategy/·broker/·worker)가 거시 레짐을 안 읽는다."""
    src = _REPO_ROOT / "src" / "auto_invest"
    for sub in ("strategy", "broker"):
        for py in (src / sub).rglob("*.py"):
            assert "macro_regime" not in py.read_text(encoding="utf-8"), py


def test_workflow_wires_regime_report_into_sidecar() -> None:
    wf = (_REPO_ROOT / ".github" / "workflows" / "collect-public-data.yml").read_text(
        encoding="utf-8"
    )
    assert "auto-invest macro-regime" in wf
    assert "regime.json" in wf
    # 보고 실패가 데이터 발행을 막지 않는다 (fail-soft)
    assert "--timeline-out /tmp/public-data/regime_timeline.csv || true" in wf
    # 모듈 변경 시 같은 날 실전 검증 (push 경로 포함)
    assert "src/auto_invest/market_data/macro_regime.py" in wf


def test_report_source_paths_match_channel_config() -> None:
    """보고서가 읽는 파일명이 채널 설정의 발행 식별자와 정합."""
    import tomllib

    cfg = tomllib.loads((_REPO_ROOT / "deploy" / "public-data.toml").read_text(encoding="utf-8"))
    spread_id = cfg["treasury"]["spread"]["id"]
    assert f"treasury/{spread_id}.csv" == SPREAD_CSV
    assert cfg["cboe"]["vix"] is True and VIX_CSV == "cboe/VIX.csv"
    bls = set(cfg["bls"]["series"])
    assert CPI_CSV.split("/")[1].removesuffix(".csv") in bls
    assert UNEMPLOYMENT_CSV.split("/")[1].removesuffix(".csv") in bls


# ---------- 이력 시계열 (시점 기준 타임라인) ----------


def _days(n: int, start_day: int = 1) -> list[str]:
    return [f"2026-06-{start_day + i:02d}" for i in range(n)]


def test_timeline_point_in_time_cpi_switch_no_lookahead() -> None:
    """월간 CPI 는 발표 지연 이후에만 라벨에 반영 — 미래 누출 차단의 핵심."""
    from auto_invest.market_data.macro_regime import daily_regime_timeline

    days = _days(8)
    spread = [(d, Decimal("0.6")) for d in days]  # NORMAL — 깃발 없음
    vix = [(d, Decimal("10")) for d in days]  # CALM — 깃발 없음
    cpi = [
        ("2025-05-01", Decimal("300")),
        ("2025-06-01", Decimal("300")),
        ("2026-05-01", Decimal("308")),  # YoY 2.67% MODERATE — 발효 06-05(지연 4일... 5월)
        ("2026-06-01", Decimal("312")),  # YoY 4.00% HIGH — 발효 2026-06-05
    ]
    rows = daily_regime_timeline(spread, vix, cpi, [], publication_lag_days=4)
    by_date = {r["date"]: r for r in rows}
    # 06-04 까지는 5월분(MODERATE, 깃발 없음) → RISK_ON
    assert by_date["2026-06-04"]["label"] == "RISK_ON"
    assert by_date["2026-06-04"]["inflation_yoy"] == "2.67"
    # 06-05 부터 6월분(HIGH, 깃발) 발효 → CAUTION
    assert by_date["2026-06-05"]["label"] == "CAUTION"
    assert by_date["2026-06-05"]["flags"] == "inflation"
    assert by_date["2026-06-05"]["inflation_yoy"] == "4.00"
    # 삼 룰 미가용 → 가용 지표 3 (일간 2 + 물가)
    assert by_date["2026-06-05"]["available"] == 3


def test_timeline_risk_off_with_two_flags_and_sahm() -> None:
    from auto_invest.market_data.macro_regime import daily_regime_timeline

    days = _days(3)
    spread = [(d, Decimal("0.6")) for d in days]
    vix = [(d, Decimal("30")) for d in days]  # ELEVATED — 깃발 1
    # 16개월(2025-02~2026-05) — 지연 1일이면 마지막 달도 06-01 이전 발효
    une = _points(["4.0"] * 13 + ["4.6", "4.8", "5.0"], start_month=(2025, 2))
    rows = daily_regime_timeline(spread, vix, [], [(d, v) for d, v in une], publication_lag_days=1)
    assert all(r["label"] == "RISK_OFF" for r in rows)  # vix + sahm = 깃발 2
    assert all("sahm" in r["flags"] and "vix" in r["flags"] for r in rows)


def test_timeline_axis_is_daily_intersection() -> None:
    from auto_invest.market_data.macro_regime import daily_regime_timeline

    spread = [(d, Decimal("0.6")) for d in _days(3)]
    vix = [(d, Decimal("10")) for d in _days(3) if d != "2026-06-02"]
    rows = daily_regime_timeline(spread, vix, [], [])
    assert [r["date"] for r in rows] == ["2026-06-01", "2026-06-03"]
    assert all(r["available"] == 2 and r["label"] == "RISK_ON" for r in rows)


def test_build_regime_timeline_from_dir_and_csv_roundtrip(tmp_path: Path) -> None:
    from auto_invest.market_data.macro_regime import (
        build_regime_timeline,
        timeline_to_csv,
    )

    days = _days(3)
    _write(tmp_path, SPREAD_CSV, _series_csv([(d, "-0.1") for d in days]))
    _write(tmp_path, VIX_CSV, _series_csv([(d, "40") for d in days]))
    rows = build_regime_timeline(tmp_path)
    assert len(rows) == 3 and rows[0]["label"] == "RISK_OFF"  # 역전 + 위기 VIX
    text = timeline_to_csv(rows)
    assert text.splitlines()[0] == ("date,label,flags,available,spread,vix,inflation_yoy,sahm_pp")
    assert "2026-06-01,RISK_OFF,yield_curve;vix,2,-0.1,40,," in text


def test_workflow_wires_timeline_into_sidecar() -> None:
    wf = (_REPO_ROOT / ".github" / "workflows" / "collect-public-data.yml").read_text(
        encoding="utf-8"
    )
    assert "--timeline-out /tmp/public-data/regime_timeline.csv" in wf
    assert "regime_timeline.csv    # 일별 레짐 이력" in wf
