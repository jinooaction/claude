"""bars-export → ingest-history → backtest-portfolio(--equity-out) → regime-stratify 체인.

레짐 층화의 첫 실제 소비를 위한 다리들을 검증한다:
  ① `bars-export` — 인스턴스 DB 의 일봉을 ohlcv-csv.md 계약 CSV 로 내보낸다(읽기 전용).
  ② `--equity-out` — 백테스트의 일별 시가평가 자본 곡선을 date,value CSV 로 저장.
  ③ 그 CSV 가 `regime-stratify` 입력으로 그대로 소비된다(전망적 d+1 결합).

그리고 **단일 잣대 회귀(헌법 X.2)**: 백테스트 리플레이가 라이브 리밸런서와 같은
추세 변환(`strategy.trend.spec_from_filter_config`)을 쓰는지 — 과거 리플레이는
`ensemble_windows`(스펙 048)를 조용히 무시하고 단일 속도만 적용해, 배포된 전략과
*다른* 전략을 재생했다. 여기 행동 테스트가 그 회귀를 막는다.

전부 합성 데이터 — 주문 0건, 돈 0 이동, 네트워크 0.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import exchange_calendars as _xcals
from typer.testing import CliRunner

from auto_invest.cli import app
from auto_invest.config.rules import TrendFilterConfig
from auto_invest.market_data.store import PriceBar, insert_bar
from auto_invest.persistence import db
from auto_invest.strategy.trend import (
    TrendEnsembleSpec,
    TrendSpec,
    spec_from_filter_config,
)

runner = CliRunner()

_N = 60
# 리플레이는 세션 날짜를 NYSE 달력으로 검증한다 — 합성 시계열도 실제 세션에 시드.
# (최근 데이터 — recency 가드 통과.)
_SESSIONS: list[date] = [
    s.date() for s in _xcals.get_calendar("XNYS").sessions_in_range("2026-02-02", "2026-05-29")
][:_N]
assert len(_SESSIONS) == _N


def _iso(d: date) -> str:
    return f"{d.isoformat()}T00:00:00.000Z"


def _seed_series(conn, symbol: str, closes: list[float]) -> None:
    for i, c in enumerate(closes):
        px = Decimal(str(round(c, 4)))
        insert_bar(
            conn,
            PriceBar(
                symbol=symbol,
                timeframe="1d",
                bar_open_utc=_iso(_SESSIONS[i]),
                open_usd=px,
                high_usd=px,
                low_usd=px,
                close_usd=px,
                volume=1000,
            ),
        )


def _decline_then_bounce() -> list[float]:
    """50일 하락(200→102) 후 10일 반등(→112).

    마지막 시점에 SMA(5) 위 / SMA(50) 아래 — 앙상블 (5,50) 분수 노출 0.5,
    단일 속도 lookback=50 이진 게이트로는 현금(0). 두 설정의 행동이 갈린다.
    """
    out = [200.0 - 2.0 * i for i in range(50)]  # 200 → 102
    out += [100.0 + 1.2 * (i + 1) for i in range(10)]  # 101.2 → 112
    return out


def _steady_riser() -> list[float]:
    return [100.0 + 1.0 * i for i in range(_N)]  # 100 → 159 (모든 추세 위)


def _seed_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "bars.db"
    conn = db.get_connection(db_path)
    db.migrate(conn)
    _seed_series(conn, "AAA", _decline_then_bounce())
    _seed_series(conn, "BBB", _steady_riser())
    conn.close()
    return db_path


def _write_portfolio(tmp_path: Path, name: str, trend_filter_toml: str) -> Path:
    p = tmp_path / f"{name}.toml"
    p.write_text(
        f"""
[caps]
per_trade_pct                  = 60.0
per_symbol_pct                 = 60.0
global_exposure_pct            = 100.0
canary_capital_pct             = 5.0
canary_min_duration_days       = 10
canary_acceptance_drawdown_pct = 30.0

[whitelist]
symbols     = ["AAA", "BBB"]
accounts    = ["BACKTEST"]
# 배포 TOML(canary/global-trend)과 동일하게 LIMIT 전용 — 리플레이가 MARKET 을
# 하드코딩하던 시절엔 whitelist_gate 가 전 주문을 거부해 백테스트가 불가능했다.
order_types = ["LIMIT"]
sessions    = ["REGULAR"]

[portfolio]
id            = "stratify-test"
universe      = ["AAA", "BBB"]
weights       = {{ momentum = "1.0" }}
weight_scheme = "equal"
top_n         = 2
lookback_bars   = 30
momentum_period = 10

{trend_filter_toml}
""",
        encoding="utf-8",
    )
    return p


_ENSEMBLE_FILTER = """
[portfolio.trend_filter]
method           = "sma"
lookback         = 50
on_insufficient  = "cash"
ensemble_windows = [5, 50]
"""

_SINGLE_FILTER = """
[portfolio.trend_filter]
method          = "sma"
lookback        = 50
on_insufficient = "cash"
"""

# 리플레이 구간: 마지막 5 영업일(반등 구간) — 이전 55봉이 룩백을 공급한다.
_FROM = _SESSIONS[55].isoformat()
_TO = _SESSIONS[59].isoformat()


def _run_chain(tmp_path: Path, trend_filter_toml: str, tag: str) -> dict:
    """bars-export → ingest → backtest-portfolio(--equity-out --json) 한 바퀴."""
    db_path = tmp_path / "bars.db"
    bars_dir = tmp_path / f"bars_{tag}"
    hist_dir = tmp_path / f"hist_{tag}"

    res = runner.invoke(
        app,
        [
            "bars-export",
            "--symbols", "AAA,BBB",
            "--db", str(db_path),
            "--out-dir", str(bars_dir),
            "--json",
        ],
    )
    assert res.exit_code == 0, res.output

    res = runner.invoke(
        app,
        [
            "ingest-history",
            "--from-dir", str(bars_dir),
            "--out-dir", str(hist_dir),
        ],
    )
    assert res.exit_code == 0, res.output

    port = _write_portfolio(tmp_path, f"port_{tag}", trend_filter_toml)
    equity_csv = tmp_path / f"equity_{tag}.csv"
    res = runner.invoke(
        app,
        [
            "backtest-portfolio",
            "--portfolio", str(port),
            "--from", _FROM,
            "--to", _TO,
            "--history-root", str(hist_dir),
            "--db", str(tmp_path / f"audit_{tag}.db"),
            "--halt-path", str(tmp_path / f"halt_{tag}.flag"),
            "--capital", "10000",
            "--equity-out", str(equity_csv),
            "--json",
        ],
    )
    assert res.exit_code == 0, res.output
    payload = json.loads(res.output.strip().splitlines()[-1])
    payload["_equity_csv"] = equity_csv
    return payload


# ───────────────────────── spec_from_filter_config (공유 변환) ─────────────────────────


def test_spec_from_filter_config_none_is_none():
    assert spec_from_filter_config(None) is None


def test_spec_from_filter_config_builds_ensemble_when_windows_set():
    tf = TrendFilterConfig(
        method="sma",
        lookback=50,
        on_insufficient="cash",
        ensemble_windows=(5, 50),
    )
    spec = spec_from_filter_config(tf)
    assert isinstance(spec, TrendEnsembleSpec)
    assert spec.windows == (5, 50)
    assert spec.on_insufficient == "cash"


def test_spec_from_filter_config_builds_single_speed_otherwise():
    tf = TrendFilterConfig(
        method="absolute_momentum",
        lookback=120,
        on_insufficient="hold",
        min_return_pct=Decimal("2.5"),
    )
    spec = spec_from_filter_config(tf)
    assert isinstance(spec, TrendSpec)
    assert spec.method == "absolute_momentum"
    assert spec.lookback == 120
    assert spec.min_return == Decimal("0.025")


# ─────────────────────────────── bars-export ───────────────────────────────


def test_bars_export_contract_and_read_only(tmp_path: Path):
    db_path = _seed_db(tmp_path)
    sha_before = hashlib.sha256(db_path.read_bytes()).hexdigest()

    out_dir = tmp_path / "bars"
    res = runner.invoke(
        app,
        [
            "bars-export",
            "--symbols", "AAA,BBB,NOBARS",
            "--db", str(db_path),
            "--out-dir", str(out_dir),
            "--json",
        ],
    )
    assert res.exit_code == 0, res.output
    payload = json.loads(res.output.strip().splitlines()[-1])
    assert payload["skipped"] == ["NOBARS"]
    assert {e["symbol"] for e in payload["exported"]} == {"AAA", "BBB"}

    text = (out_dir / "AAA.csv").read_text(encoding="utf-8")
    lines = text.splitlines()
    assert lines[0] == "session_date,open,high,low,close,volume,session_schedule_tag"
    assert len(lines) == 1 + _N
    assert lines[1].startswith(f"{_SESSIONS[0].isoformat()},200")
    assert lines[1].endswith(",1000,regular")

    # 읽기 전용 — DB 파일 바이트 불변(쓰기·마이그레이션 0).
    assert hashlib.sha256(db_path.read_bytes()).hexdigest() == sha_before


def test_bars_export_exit_1_when_nothing_exported(tmp_path: Path):
    db_path = _seed_db(tmp_path)
    res = runner.invoke(
        app,
        [
            "bars-export",
            "--symbols", "NOPE",
            "--db", str(db_path),
            "--out-dir", str(tmp_path / "empty"),
        ],
    )
    assert res.exit_code == 1


# ──────────────── 단일 잣대 회귀: 리플레이가 앙상블을 존중하는가 ────────────────


def test_replay_honors_ensemble_windows(tmp_path: Path):
    """앙상블 설정(분수 0.5)이면 AAA 도 산다 — 과거 버그는 단일 속도로 강등해 현금."""
    _seed_db(tmp_path)
    ensemble = _run_chain(tmp_path, _ENSEMBLE_FILTER, "ens")
    single = _run_chain(tmp_path, _SINGLE_FILTER, "single")

    # 단일 속도(50): AAA 는 SMA(50) 아래 → BBB 만 1건 매수.
    assert single["fills"] == 1, single
    # 앙상블 (5,50): AAA 분수 0.5 → AAA·BBB 둘 다 매수(2건).
    # 리플레이가 ensemble_windows 를 무시(과거 버그)하면 여기서 1건이 된다.
    assert ensemble["fills"] == 2, ensemble
    # LIMIT 전용 화이트리스트에서 게이트 거부 0 — 배포 TOML 재생 가능(단일 잣대).
    assert ensemble["gate_rejections"] == 0, ensemble
    assert single["gate_rejections"] == 0, single


# ──────────── equity-out → regime-stratify (레짐 층화 소비 형식) ────────────


def test_equity_out_feeds_regime_stratify(tmp_path: Path):
    _seed_db(tmp_path)
    payload = _run_chain(tmp_path, _ENSEMBLE_FILTER, "strat")
    equity_csv: Path = payload["_equity_csv"]

    text = equity_csv.read_text(encoding="utf-8")
    lines = text.splitlines()
    assert lines[0] == "date,value"
    assert len(lines) == 1 + 5  # 세션당 한 점(2026-04-25 ~ 04-29)

    # 타임라인: 처음 3일 RISK_ON, 그다음 CAUTION → d+1 결합으로 RISK_ON 3 / CAUTION 1.
    tl = tmp_path / "timeline.csv"
    rows = ["date,label\n"]
    for i in range(55, 58):
        rows.append(f"{_SESSIONS[i].isoformat()},RISK_ON\n")
    for i in range(58, 60):
        rows.append(f"{_SESSIONS[i].isoformat()},CAUTION\n")
    tl.write_text("".join(rows), encoding="utf-8")

    res = runner.invoke(
        app,
        [
            "regime-stratify",
            "--returns-csv", str(equity_csv),
            "--timeline-csv", str(tl),
            "--json",
        ],
    )
    assert res.exit_code == 0, res.output
    result = json.loads(res.output.strip().splitlines()[-1])
    assert result["total_return_days"] == 4  # NAV 5점 → 수익률 4일
    by_label = result["by_label"]
    assert by_label["RISK_ON"]["n_days"] == 3
    assert by_label["CAUTION"]["n_days"] == 1
    assert "UNLABELED" not in by_label
