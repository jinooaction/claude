"""공개 데이터 수집 채널 (계획 ④) — 파싱·검증·교차 검증·수집 오케스트레이션.

네트워크 0: httpx.MockTransport 주입. 실제 Stooq/FRED 호출은 워크플로
(collect-public-data.yml)의 첫 실행이 실전 검증한다(같은 날 검증 패턴).
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import httpx
import pytest

from auto_invest.market_data.public_data import (
    USER_AGENT,
    PublicBar,
    SeriesPoint,
    bls_v1_url,
    cboe_vix_history_url,
    collect_public_data,
    cross_check_daily_returns,
    cross_check_levels,
    dbnomics_series_url,
    fetch_text,
    fred_csv_url,
    parse_bls_v1_json,
    parse_cboe_daily_csv,
    parse_dbnomics_json,
    parse_fred_csv,
    parse_stooq_daily_csv,
    parse_treasury_csv,
    stooq_daily_csv_url,
    treasury_csv_url,
    validate_daily_bars,
    validate_series,
)

AS_OF = date(2026, 6, 11)


# ---------- URL 빌더 ----------


def test_stooq_url_appends_us_suffix() -> None:
    assert stooq_daily_csv_url("SPY") == "https://stooq.com/q/d/l/?s=spy.us&i=d"


def test_stooq_url_keeps_explicit_suffix_and_index_prefix() -> None:
    assert "s=ewg.de" in stooq_daily_csv_url("EWG.DE")
    assert "s=^spx" in stooq_daily_csv_url("^SPX")


def test_stooq_url_rejects_empty() -> None:
    with pytest.raises(ValueError):
        stooq_daily_csv_url("  ")


def test_fred_url() -> None:
    assert fred_csv_url("dgs10") == "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10"


# ---------- 파서 ----------


def _stooq_csv(rows: list[str]) -> str:
    return "Date,Open,High,Low,Close,Volume\n" + "\n".join(rows)


def test_parse_stooq_happy_path_sorts_ascending() -> None:
    text = _stooq_csv(
        [
            "2026-06-10,101,103,100,102,1200",
            "2026-06-09,100,102,99,101,1000",
        ]
    )
    bars = parse_stooq_daily_csv(text)
    assert [b.date for b in bars] == ["2026-06-09", "2026-06-10"]
    assert bars[0].close_usd == Decimal("101")
    assert bars[1].volume == 1200


def test_parse_stooq_empty_volume_becomes_zero() -> None:
    bars = parse_stooq_daily_csv(_stooq_csv(["2026-06-10,1,2,0.5,1.5,"]))
    assert bars[0].volume == 0


def test_parse_stooq_no_data_raises() -> None:
    with pytest.raises(ValueError, match="No data|데이터 없음"):
        parse_stooq_daily_csv("No data")


def test_parse_stooq_html_block_page_raises() -> None:
    with pytest.raises(ValueError, match="헤더"):
        parse_stooq_daily_csv("<html><body>blocked</body></html>")


def test_parse_fred_accepts_both_header_styles_and_missing_dot() -> None:
    legacy = "DATE,DGS10\n2026-06-09,4.40\n2026-06-10,.\n"
    modern = "observation_date,DGS10\n2026-06-09,4.40\n2026-06-10,.\n"
    for text in (legacy, modern):
        points = parse_fred_csv(text)
        assert points[0].value == Decimal("4.40")
        assert points[1].value is None


def test_parse_fred_bad_header_raises() -> None:
    with pytest.raises(ValueError, match="헤더"):
        parse_fred_csv("symbol,value\nSPY,1\n")


# ---------- 일봉 검증 ----------


def _bars(n: int, *, end: date = AS_OF, close: Decimal = Decimal("100")) -> list[PublicBar]:
    out = []
    for i in range(n):
        d = (end - timedelta(days=n - 1 - i)).isoformat()
        out.append(
            PublicBar(
                date=d, open_usd=close, high_usd=close + 1, low_usd=close - 1,
                close_usd=close, volume=1000,
            )
        )
    return out


def test_validate_daily_bars_ok() -> None:
    v = validate_daily_bars(_bars(30), as_of=AS_OF, min_rows=10)
    assert v.ok and v.rows == 30 and not v.issues


def test_validate_daily_bars_too_few_rows() -> None:
    v = validate_daily_bars(_bars(5), as_of=AS_OF, min_rows=10)
    assert not v.ok and any("행 부족" in i for i in v.issues)


def test_validate_daily_bars_stale() -> None:
    v = validate_daily_bars(
        _bars(30, end=AS_OF - timedelta(days=30)), as_of=AS_OF, min_rows=10
    )
    assert not v.ok and any("신선도" in i for i in v.issues)


def test_validate_daily_bars_gap() -> None:
    bars = _bars(10, end=AS_OF - timedelta(days=20)) + _bars(10)
    v = validate_daily_bars(bars, as_of=AS_OF, min_rows=10, max_gap_days=5)
    assert not v.ok and any("공백" in i for i in v.issues)


def test_validate_daily_bars_ohlc_violation_and_nonpositive() -> None:
    bad = _bars(10)[:-1] + [
        PublicBar(
            date=AS_OF.isoformat(), open_usd=Decimal("100"), high_usd=Decimal("90"),
            low_usd=Decimal("95"), close_usd=Decimal("-1"), volume=0,
        )
    ]
    v = validate_daily_bars(bad, as_of=AS_OF, min_rows=5)
    assert not v.ok
    assert any("OHLC" in i for i in v.issues)
    assert any("0 이하" in i for i in v.issues)


def test_validate_daily_bars_jump_anomaly() -> None:
    bars = _bars(10)
    last = bars[-1]
    bars[-1] = PublicBar(
        date=last.date, open_usd=last.open_usd, high_usd=Decimal("300"),
        low_usd=last.low_usd, close_usd=Decimal("200"), volume=last.volume,
    )
    v = validate_daily_bars(bars, as_of=AS_OF, min_rows=5)
    assert not v.ok and any("이상치" in i for i in v.issues)


def test_validate_series_ok_and_stale() -> None:
    pts = [
        SeriesPoint(date=(AS_OF - timedelta(days=40 - i)).isoformat(), value=Decimal(i + 1))
        for i in range(30)
    ]
    assert validate_series(pts, as_of=AS_OF, min_rows=10).ok
    old = [
        SeriesPoint(date=(AS_OF - timedelta(days=400 - i)).isoformat(), value=Decimal(1))
        for i in range(30)
    ]
    v = validate_series(old, as_of=AS_OF, min_rows=10, max_staleness_days=70)
    assert not v.ok and any("신선도" in i for i in v.issues)


def test_validate_series_all_missing() -> None:
    pts = [SeriesPoint(date="2026-06-01", value=None)]
    v = validate_series(pts, as_of=AS_OF, min_rows=1)
    assert not v.ok and any("결측" in i for i in v.issues)


# ---------- 교차 검증 (두 소스 일일 수익률) ----------


def _closes(n: int, *, jump_at: set[int] | None = None) -> dict[str, Decimal]:
    out: dict[str, Decimal] = {}
    px = Decimal("100")
    for i in range(n):
        d = (AS_OF - timedelta(days=n - 1 - i)).isoformat()
        px = px * (Decimal("1.05") if jump_at and i in jump_at else Decimal("1.001"))
        out[d] = px
    return out


def test_cross_check_identical_returns_pass() -> None:
    a = _closes(80)
    b = {d: v * 10 for d, v in a.items()}  # 수준은 10배 달라도 수익률은 동일
    cc = cross_check_daily_returns(a, b, min_overlap_returns=50)
    assert cc.status == "PASS" and cc.agree_pct == "100.00"


def test_cross_check_few_divergences_still_pass() -> None:
    a = _closes(101)
    b = _closes(101, jump_at={50})  # 100개 수익률 중 1개만 어긋남 (99% 일치)
    cc = cross_check_daily_returns(a, b, min_overlap_returns=50)
    assert cc.status == "PASS"


def test_cross_check_many_divergences_fail() -> None:
    a = _closes(101)
    b = _closes(101, jump_at=set(range(10, 90, 4)))
    cc = cross_check_daily_returns(a, b, min_overlap_returns=50)
    assert cc.status == "FAIL"


def test_cross_check_insufficient_overlap() -> None:
    cc = cross_check_daily_returns(_closes(5), _closes(5), min_overlap_returns=50)
    assert cc.status == "INSUFFICIENT_OVERLAP"


# ---------- fetch_text 재시도 ----------


def test_fetch_text_retries_5xx_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("auto_invest.market_data.public_data.time.sleep", lambda _s: None)
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(503, text="busy")
        return httpx.Response(200, text="ok-body")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert fetch_text(client, "https://example.com/x") == "ok-body"
    assert calls["n"] == 3


def test_fetch_text_4xx_no_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("auto_invest.market_data.public_data.time.sleep", lambda _s: None)
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(404, text="nope")

    with (
        httpx.Client(transport=httpx.MockTransport(handler)) as client,
        pytest.raises(httpx.HTTPStatusError),
    ):
        fetch_text(client, "https://example.com/x")
    assert calls["n"] == 1


def test_fetch_text_can_use_httpx_default_user_agent() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers.get("user-agent", ""))
        return httpx.Response(200, text="ok")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert fetch_text(client, "https://fred.stlouisfed.org/x", user_agent=None) == "ok"
    assert seen and seen[0].startswith("python-httpx/")
    assert seen[0] != USER_AGENT


# ---------- 수집 오케스트레이션 (발행 게이트 + fail-soft + 교차 검증 연결) ----------


def _stooq_body(n: int, *, end: date = AS_OF) -> str:
    rows = []
    px = Decimal("100")
    for i in range(n):
        d = (end - timedelta(days=n - 1 - i)).isoformat()
        px *= Decimal("1.001")
        rows.append(f"{d},{px},{px + 1},{px - 1},{px},1000")
    return _stooq_csv(rows)


def _fred_body(series: str, n: int, *, end: date = AS_OF) -> str:
    lines = [f"observation_date,{series}"]
    px = Decimal("100")
    for i in range(n):
        d = (end - timedelta(days=n - 1 - i)).isoformat()
        px *= Decimal("1.001")
        lines.append(f"{d},{px}")
    return "\n".join(lines)


def _config() -> dict:
    return {
        "stooq": {"symbols": ["SPY", "IEF"], "min_rows": 50, "max_staleness_days": 7},
        "fred": {"series": ["SP500", "DGS10"], "min_rows": 24, "max_staleness_days": 70},
        "cross_checks": [
            {
                "kind": "returns",
                "a": "stooq:SPY",
                "b": "fred:SP500",
                "tolerance_pct": "0.5",
                "min_overlap": 60,
                "min_agree_pct": "95",
            }
        ],
    }


def _run_collect(handler, tmp_path: Path) -> dict:
    out_dir = tmp_path / "out"
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        return collect_public_data(client, _config(), out_dir=out_dir, as_of=AS_OF)


def test_collect_happy_path_publishes_all_and_cross_check_passes(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "stooq.com":
            return httpx.Response(200, text=_stooq_body(100))
        series = request.url.params["id"]
        return httpx.Response(200, text=_fred_body(series, 100))

    summary = _run_collect(handler, tmp_path)
    assert summary["overall_ok"] is True
    assert summary["published"] == 4
    assert summary["cross_checks"][0]["status"] == "PASS"
    out_dir = tmp_path / "out"
    spy = (out_dir / "stooq" / "SPY.csv").read_text(encoding="utf-8")
    assert spy.splitlines()[0] == "date,open,high,low,close,volume"
    assert (out_dir / "fred" / "DGS10.csv").exists()
    on_disk = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
    assert on_disk["overall_ok"] is True


def test_collect_failing_item_is_quarantined_not_published(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "stooq.com":
            if "ief" in str(request.url.params["s"]):
                # IEF 만 60일 묵은 데이터 → 신선도 위반 → 미발행 (fail-soft)
                return httpx.Response(
                    200, text=_stooq_body(100, end=AS_OF - timedelta(days=60))
                )
            return httpx.Response(200, text=_stooq_body(100))
        series = request.url.params["id"]
        return httpx.Response(200, text=_fred_body(series, 100))

    summary = _run_collect(handler, tmp_path)
    assert summary["overall_ok"] is False  # 한 항목이라도 실패면 전체 깃발은 내려간다
    assert summary["published"] == 3
    assert not (tmp_path / "out" / "stooq" / "IEF.csv").exists()
    ief = next(i for i in summary["items"] if i["id"] == "IEF")
    assert ief["ok"] is False and any("신선도" in s for s in ief["issues"])


def test_collect_network_error_is_failsoft_per_item(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "stooq.com":
            return httpx.Response(404, text="No data")
        series = request.url.params["id"]
        return httpx.Response(200, text=_fred_body(series, 100))

    summary = _run_collect(handler, tmp_path)
    assert summary["published"] == 2  # FRED 두 시리즈만
    assert summary["cross_checks"][0]["status"] == "SKIPPED"  # SPY 미발행 → 짝 없음
    assert all(not i["ok"] for i in summary["items"] if i["kind"] == "stooq")


def test_collect_time_budget_exhausted_skips_items_but_publishes_summary(
    tmp_path: Path,
) -> None:
    """타르핏 방어 — 예산 0 이면 전 항목 미시도로 기록하되 summary 는 반드시 발행."""

    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover - 미호출
        raise AssertionError("예산 0 에서는 어떤 수집 요청도 나가면 안 된다")

    cfg = _config()
    cfg["collection"] = {"time_budget_seconds": 0}
    out_dir = tmp_path / "out"
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        summary = collect_public_data(client, cfg, out_dir=out_dir, as_of=AS_OF)
    assert summary["published"] == 0 and summary["overall_ok"] is False
    assert all(any("시간 예산" in s for s in i["issues"]) for i in summary["items"])
    assert (out_dir / "summary.json").exists()


def test_collect_records_probes_with_both_user_agents(tmp_path: Path) -> None:
    seen_uas: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "probe.example.com":
            seen_uas.append(request.headers.get("user-agent", ""))
            return httpx.Response(200, content=b"PK\x03\x04binary-zip-head")
        if request.url.host == "stooq.com":
            return httpx.Response(200, text=_stooq_body(100))
        return httpx.Response(200, text=_fred_body(request.url.params["id"], 100))

    cfg = _config()
    cfg["probes"] = {"urls": ["https://probe.example.com/bulk.zip"]}
    out_dir = tmp_path / "out"
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        summary = collect_public_data(client, cfg, out_dir=out_dir, as_of=AS_OF)
    probes = summary["probes"]
    assert len(probes) == 2
    assert {p["user_agent"] for p in probes} == {"channel", "httpx-default"}
    assert all(p["status"] == 200 and p["ok"] for p in probes)
    assert all("elapsed_ms" in p and "content_head" in p for p in probes)
    # 바이너리 머리도 JSON 안전하게 기록(비인쇄 문자는 치환).
    assert "PK" in probes[0]["content_head"]
    # 탐침이 수집을 오염시키지 않는다 — 항목 발행은 그대로.
    assert summary["published"] == 4 and summary["overall_ok"] is True


def test_probe_url_failure_never_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    from auto_invest.market_data.public_data import probe_url

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        out = probe_url(client, "https://x.example.com/", user_agent=None)
    assert out["ok"] is False and "ConnectError" in out["error"]


def test_collect_cross_check_divergence_fails_overall(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "stooq.com":
            return httpx.Response(200, text=_stooq_body(100))
        series = request.url.params["id"]
        if series == "SP500":
            # 같은 날짜인데 수익률 패턴이 전혀 다른 시리즈 → 교차 검증 FAIL
            lines = [f"observation_date,{series}"]
            px = Decimal("100")
            for i in range(100):
                d = (AS_OF - timedelta(days=99 - i)).isoformat()
                px *= Decimal("1.05") if i % 2 else Decimal("0.96")
                lines.append(f"{d},{px}")
            return httpx.Response(200, text="\n".join(lines))
        return httpx.Response(200, text=_fred_body(series, 100))

    summary = _run_collect(handler, tmp_path)
    assert summary["cross_checks"][0]["status"] == "FAIL"
    assert summary["overall_ok"] is False
    # 데이터 자체는 발행됨(귀속 불가) — 소비자는 summary 의 FAIL 을 보고 거른다.
    assert summary["published"] == 4


# ---------- 4차: 공식 키리스 소스 (재무부·Cboe·BLS·DBnomics) ----------


def test_official_source_urls() -> None:
    assert treasury_csv_url(2026) == (
        "https://home.treasury.gov/resource-center/data-chart-center/"
        "interest-rates/daily-treasury-rates.csv/2026/all"
        "?type=daily_treasury_yield_curve&field_tdr_date_value=2026&page&_format=csv"
    )
    assert cboe_vix_history_url().endswith("/VIX_History.csv")
    assert bls_v1_url("LNS14000000").endswith("/timeseries/data/LNS14000000")
    assert dbnomics_series_url("BLS/cu/CUUR0000SA0") == (
        "https://api.db.nomics.world/v22/series/BLS/cu/CUUR0000SA0"
        "?observations=1&format=json"
    )
    with pytest.raises(ValueError):
        bls_v1_url("  ")
    with pytest.raises(ValueError):
        dbnomics_series_url("")


def test_parse_treasury_csv_wide_to_series() -> None:
    text = (
        'Date,"1 Mo","2 Yr","10 Yr"\n'
        "06/11/2026,4.30,3.90,4.40\n"
        "06/10/2026,4.31,,4.39\n"
    )
    out = parse_treasury_csv(text)
    assert set(out) == {"1 Mo", "2 Yr", "10 Yr"}
    ten = out["10 Yr"]
    assert [p.date for p in ten] == ["2026-06-10", "2026-06-11"]  # 오름차순 정렬
    assert ten[1].value == Decimal("4.40")
    assert out["2 Yr"][0].value is None  # 빈 칸 → 결측 보존


def test_parse_treasury_csv_bad_header_raises() -> None:
    with pytest.raises(ValueError):
        parse_treasury_csv("<html>blocked</html>")


def test_parse_cboe_daily_csv_sorts_and_zero_volume() -> None:
    text = (
        "DATE,OPEN,HIGH,LOW,CLOSE\n"
        "01/02/2026,17.6,18.2,17.0,17.2\n"
        "01/01/2026,17.0,17.5,16.8,17.1\n"
    )
    bars = parse_cboe_daily_csv(text)
    assert [b.date for b in bars] == ["2026-01-01", "2026-01-02"]
    assert bars[0].volume == 0 and bars[1].close_usd == Decimal("17.2")
    with pytest.raises(ValueError):
        parse_cboe_daily_csv("not,a,vix,file\n1,2,3,4")


def test_parse_bls_v1_json_skips_annual_and_sorts() -> None:
    payload = {
        "status": "REQUEST_SUCCEEDED",
        "Results": {
            "series": [
                {
                    "data": [
                        {"year": "2026", "period": "M05", "value": "4.1"},
                        {"year": "2026", "period": "M13", "value": "9.9"},  # 연간 집계
                        {"year": "2026", "period": "M04", "value": "4.2"},
                        {"year": "2025", "period": "M10", "value": "-"},  # 미발표 결측
                    ]
                }
            ]
        },
    }
    points = parse_bls_v1_json(json.dumps(payload))
    assert [(p.date, p.value) for p in points] == [
        ("2025-10-01", None),  # "-" 는 결측 보존 (2025-10 정부 셧다운 실측)
        ("2026-04-01", Decimal("4.2")),
        ("2026-05-01", Decimal("4.1")),
    ]


def test_parse_bls_v1_json_failure_status_raises() -> None:
    with pytest.raises(ValueError):
        parse_bls_v1_json(json.dumps({"status": "REQUEST_NOT_PROCESSED"}))


def test_parse_dbnomics_json_normalizes_monthly_and_na() -> None:
    payload = {"series": {"docs": [{"period": ["2026-04", "2026-05"], "value": [320.5, "NA"]}]}}
    points = parse_dbnomics_json(json.dumps(payload))
    assert points[0] == SeriesPoint(date="2026-04-01", value=Decimal("320.5"))
    assert points[1].value is None
    with pytest.raises(ValueError):
        parse_dbnomics_json(json.dumps({"series": {"docs": []}}))


def test_parse_dbnomics_json_daily_periods_kept_verbatim() -> None:
    """H.15 같은 일간 시리즈의 'YYYY-MM-DD' 는 그대로 보존된다 (월간만 정규화)."""
    payload = {
        "series": {"docs": [{"period": ["2026-06-10", "2026-06-11"], "value": [4.40, "NA"]}]}
    }
    points = parse_dbnomics_json(json.dumps(payload))
    assert points[0] == SeriesPoint(date="2026-06-10", value=Decimal("4.4"))
    assert points[1] == SeriesPoint(date="2026-06-11", value=None)


def test_cross_check_levels_pass_fail_and_overlap() -> None:
    a = {f"2026-{m:02d}-01": Decimal("100") + m for m in range(1, 13)}
    assert cross_check_levels(a, dict(a)).status == "PASS"
    b = dict(a)
    b["2026-06-01"] += Decimal("5")  # 미러 대조는 한 점만 어긋나도 FAIL (합격선 100%)
    assert cross_check_levels(a, b).status == "FAIL"
    assert cross_check_levels(a, {}, min_overlap=1).status == "INSUFFICIENT_OVERLAP"


def _treasury_body(*, end: date, days: int = 80) -> str:
    rows = []
    for i in range(days):
        d = end - timedelta(days=i)  # 원본은 최신 먼저
        rows.append(f"{d.month:02d}/{d.day:02d}/{d.year},3.90,4.40")
    return 'Date,"2 Yr","10 Yr"\n' + "\n".join(rows)


def _cboe_body(*, end: date, days: int = 80) -> str:
    rows = []
    for i in range(days):
        d = end - timedelta(days=days - 1 - i)
        rows.append(f"{d.month:02d}/{d.day:02d}/{d.year},17.0,18.0,16.5,17.5")
    return "DATE,OPEN,HIGH,LOW,CLOSE\n" + "\n".join(rows)


def _cpi_value(y: int, m: int) -> Decimal:
    return Decimal(y * 12 + m) / 10


def _last_months(n: int, *, end_y: int = 2026, end_m: int = 5) -> list[tuple[int, int]]:
    out, y, m = [], end_y, end_m
    for _ in range(n):
        out.append((y, m))
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return list(reversed(out))


def _bls_body(series_id: str) -> str:
    data = [
        {"year": str(y), "period": f"M{m:02d}", "value": str(_cpi_value(y, m))}
        for (y, m) in _last_months(24)
    ]
    return json.dumps(
        {"status": "REQUEST_SUCCEEDED", "Results": {"series": [{"data": data}]}}
    )


def _dbnomics_body() -> str:
    months = _last_months(24)
    return json.dumps(
        {
            "series": {
                "docs": [
                    {
                        "period": [f"{y:04d}-{m:02d}" for (y, m) in months],
                        "value": [float(_cpi_value(y, m)) for (y, m) in months],
                    }
                ]
            }
        }
    )


def _dbnomics_h15_body(value: str, *, end: date, days: int = 80) -> str:
    """연준 H.15 일간 금리 미러 — 재무부 모의 응답(_treasury_body)과 같은 값."""
    ds = [end - timedelta(days=i) for i in range(days)]
    return json.dumps(
        {
            "series": {
                "docs": [
                    {
                        "period": [d.isoformat() for d in sorted(ds)],
                        "value": [float(value)] * days,
                    }
                ]
            }
        }
    )


def _fred_rate_body(series: str, value: str, *, end: date, days: int = 80) -> str:
    """FRED 그래프 CSV 금리 — 재무부 모의 응답(_treasury_body)과 같은 값."""
    rows = []
    for i in range(days):
        d = end - timedelta(days=days - 1 - i)
        rows.append(f"{d.isoformat()},{value}")
    return f"observation_date,{series}\n" + "\n".join(rows)


def _official_config() -> dict:
    return {
        "treasury": {
            "years_back": 1,
            "min_rows": 50,
            "max_staleness_days": 7,
            "maturities": {"2 Yr": "UST2Y", "10 Yr": "UST10Y"},
            "spread": {"id": "UST10Y2Y", "long": "10 Yr", "short": "2 Yr"},
        },
        "fred": {
            "series": ["DGS2", "DGS10"],
            "min_rows": 50,
            "max_staleness_days": 7,
            "user_agent": "httpx-default",
        },
        "cboe": {"vix": True, "min_rows": 50, "max_staleness_days": 7},
        "bls": {"series": ["LNS14000000", "CUUR0000SA0"], "min_rows": 12},
        "dbnomics": {
            "series": [
                "BLS/cu/CUUR0000SA0",
                "FED/H15/RIFLGFCY02_N.B",
                "FED/H15/RIFLGFCY10_N.B",
            ],
            "min_rows": 12,
        },
        "cross_checks": [
            {
                "kind": "levels",
                "a": "bls:CUUR0000SA0",
                "b": "dbnomics:BLS/cu/CUUR0000SA0",
                "tolerance": "0.001",
                "min_overlap": 12,
            },
            {
                "kind": "levels",
                "a": "treasury:UST2Y",
                "b": "dbnomics:FED/H15/RIFLGFCY02_N.B",
                "tolerance": "0.001",
                "min_overlap": 60,
                "min_agree_pct": "99.5",
            },
            {
                "kind": "levels",
                "a": "treasury:UST10Y",
                "b": "dbnomics:FED/H15/RIFLGFCY10_N.B",
                "tolerance": "0.001",
                "min_overlap": 60,
                "min_agree_pct": "99.5",
            },
            {
                "kind": "levels",
                "a": "treasury:UST2Y",
                "b": "fred:DGS2",
                "tolerance": "0.001",
                "min_overlap": 60,
                "min_agree_pct": "99.5",
            },
            {
                "kind": "levels",
                "a": "treasury:UST10Y",
                "b": "fred:DGS10",
                "tolerance": "0.001",
                "min_overlap": 60,
                "min_agree_pct": "99.5",
            },
        ],
    }


def _official_handler(request: httpx.Request) -> httpx.Response:
    host = request.url.host
    if host == "home.treasury.gov":
        return httpx.Response(200, text=_treasury_body(end=AS_OF))
    if host == "cdn.cboe.com":
        return httpx.Response(200, text=_cboe_body(end=AS_OF))
    if host == "api.bls.gov":
        return httpx.Response(200, text=_bls_body(request.url.path.rsplit("/", 1)[-1]))
    if host == "api.db.nomics.world":
        path = request.url.path
        if "RIFLGFCY02_N.B" in path:
            return httpx.Response(200, text=_dbnomics_h15_body("3.90", end=AS_OF))
        if "RIFLGFCY10_N.B" in path:
            return httpx.Response(200, text=_dbnomics_h15_body("4.40", end=AS_OF))
        return httpx.Response(200, text=_dbnomics_body())
    if host == "fred.stlouisfed.org":
        series = request.url.params["id"]
        if series == "DGS2":
            return httpx.Response(200, text=_fred_rate_body(series, "3.90", end=AS_OF))
        if series == "DGS10":
            return httpx.Response(200, text=_fred_rate_body(series, "4.40", end=AS_OF))
    raise AssertionError(f"예상 밖 호출: {request.url}")


def test_collect_official_sources_happy_path(tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    with httpx.Client(transport=httpx.MockTransport(_official_handler)) as client:
        summary = collect_public_data(
            client, _official_config(), out_dir=out_dir, as_of=AS_OF
        )
    assert summary["overall_ok"] is True
    # UST2Y + UST10Y + 파생 스프레드 + FRED 2종 + VIX + BLS 2종 + DBnomics 3종 = 11
    assert summary["published"] == 11
    # CPI 미러 + 금리 대조 4건(DBnomics H.15 2건, FRED 2건) — 전부 PASS
    assert [c["status"] for c in summary["cross_checks"]] == [
        "PASS",
        "PASS",
        "PASS",
        "PASS",
        "PASS",
    ]
    spread = (out_dir / "treasury" / "UST10Y2Y.csv").read_text(encoding="utf-8")
    assert ",0.50" in spread  # 4.40 - 3.90
    # VIX 는 종가 시계열로 발행 (1990년대 초 원본 OHLC 정합 깨짐 실측 대응)
    vix = (out_dir / "cboe" / "VIX.csv").read_text(encoding="utf-8")
    assert vix.splitlines()[0] == "date,value"
    assert (out_dir / "bls" / "CUUR0000SA0.csv").exists()
    assert (out_dir / "fred" / "DGS2.csv").exists()
    assert (out_dir / "fred" / "DGS10.csv").exists()
    assert (out_dir / "dbnomics" / "BLS_CU_CUUR0000SA0.csv").exists()
    assert (out_dir / "dbnomics" / "FED_H15_RIFLGFCY10_N.B.csv").exists()


def test_collect_fred_uses_configured_default_user_agent(tmp_path: Path) -> None:
    fred_uas: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "fred.stlouisfed.org":
            fred_uas.append(request.headers.get("user-agent", ""))
        return _official_handler(request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        collect_public_data(
            client, _official_config(), out_dir=tmp_path / "out", as_of=AS_OF
        )
    assert len(fred_uas) == 2
    assert all(ua.startswith("python-httpx/") and ua != USER_AGENT for ua in fred_uas)


def test_collect_official_sources_failsoft_and_spread_needs_both_legs(
    tmp_path: Path,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "home.treasury.gov":
            return httpx.Response(403, text="forbidden")  # 재무부만 죽은 날
        return _official_handler(request)

    out_dir = tmp_path / "out"
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        summary = collect_public_data(
            client, _official_config(), out_dir=out_dir, as_of=AS_OF
        )
    assert summary["overall_ok"] is False
    assert summary["published"] == 8  # FRED 2종 + VIX + BLS 2종 + DBnomics 3종은 계속 발행
    by_id = {i["id"]: i for i in summary["items"]}
    assert not by_id["UST10Y"]["ok"] and not by_id["UST2Y"]["ok"]
    assert not by_id["UST10Y2Y"]["ok"]  # 한 다리만 죽어도 스프레드는 미발행
    # CPI 짝은 영향 없음 — 금리 두-기관 대조는 재무부 다리가 죽어 SKIPPED 로 정직 표기
    assert [c["status"] for c in summary["cross_checks"]] == [
        "PASS",
        "SKIPPED",
        "SKIPPED",
        "SKIPPED",
        "SKIPPED",
    ]
