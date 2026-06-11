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
    PublicBar,
    SeriesPoint,
    collect_public_data,
    cross_check_daily_returns,
    fetch_text,
    fred_csv_url,
    parse_fred_csv,
    parse_stooq_daily_csv,
    stooq_daily_csv_url,
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
        "cross_check": {
            "stooq_symbol": "SPY",
            "fred_series": "SP500",
            "tolerance_pct": "0.5",
            "min_overlap_returns": 60,
            "min_agree_pct": "95",
        },
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
    assert summary["cross_check"]["status"] == "PASS"
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
    assert summary["cross_check"]["status"] == "SKIPPED"  # SPY 미발행 → 짝 없음
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
    assert summary["cross_check"]["status"] == "FAIL"
    assert summary["overall_ok"] is False
    # 데이터 자체는 발행됨(귀속 불가) — 소비자는 summary 의 FAIL 을 보고 거른다.
    assert summary["published"] == 4
