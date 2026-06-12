"""거시 레짐 보고서 (계획 ④ 후속 — 공개 데이터 채널의 연구 전용 소비자 1호).

공개 데이터 채널이 발행한 CSV(재무부 금리차 UST10Y2Y·Cboe VIX 종가·BLS
CPI/실업률)를 읽어 결정론적 거시 레짐 보고서(regime.json)를 만든다.

위치(데이터 흐름): collect-public-data.yml 이 수집 직후 같은 실행기에서 이
모듈을 돌려 사이드카(automation/public-data)에 발행한다. 연구·백테스트 보조
용 — 라이브 매매 신호 경로(strategy/regime.py 의 가격 레짐, KIS 데이터)와
완전히 분리된 별도 산출물이며, 어떤 라이브 모듈도 이 보고서를 읽지 않는다
(워크플로 불변식 테스트가 CI 에 고정).

지표 4종(전부 표준 정의, 결정론적 Decimal — float 없음):
  * 금리 곡선  — 10년-2년 스프레드: INVERTED(<0) / FLAT(0~0.5) / NORMAL(>0.5)
                + 최근 252 관측 중 역전 일수.
  * VIX        — 수준 구간: CALM(<15) / NORMAL(15~25) / ELEVATED(25~35) /
                CRISIS(>=35) + 전체 이력 백분위.
  * 물가       — CPI 전년동월비(YoY): DEFLATION(<0) / LOW(0~2) / MODERATE(2~3)
                / HIGH(3~5) / VERY_HIGH(>=5).
  * 고용       — 삼 룰(Sahm rule): 실업률 3개월 이동평균 − 직전 12개월 내
                3개월 이동평균 최솟값 >= 0.5%p 면 TRIGGERED (경기침체 신호).

합성: 스트레스 깃발(역전·VIX ELEVATED 이상·물가 HIGH 이상 또는 DEFLATION·삼
룰 TRIGGERED) 개수로 RISK_ON(0) / CAUTION(1) / RISK_OFF(>=2). 지표 단위
fail-soft — 파일이 없거나 계산 불가면 그 지표만 UNAVAILABLE 로 남기고
나머지로 합성한다(계산 가능 지표 2개 미만이면 INSUFFICIENT).
"""

from __future__ import annotations

import csv
import io
import json
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0"

# 채널 발행 경로 (deploy/public-data.toml 의 발행 식별자와 정합 —
# 워크플로 불변식 테스트가 설정과 대조한다).
SPREAD_CSV = "treasury/UST10Y2Y.csv"
VIX_CSV = "cboe/VIX.csv"
CPI_CSV = "bls/CUUR0000SA0.csv"
UNEMPLOYMENT_CSV = "bls/LNS14000000.csv"

SAHM_THRESHOLD = Decimal("0.5")  # 표준 삼 룰 문턱 (%p)

# 월간 거시 지표(CPI·실업률)의 발표 지연 — 기준월 종료 후 약 2주 + 여유.
# 이력 시계열(타임라인)은 "그날 알 수 있었던 값"만 쓰는 시점 기준 계산이라
# 이 지연을 적용한다(미래 정보 누출 차단). 최신 스냅숏(regime.json)은 반대로
# "지금 아는 전부"를 쓰므로 지연을 적용하지 않는다 — 둘이 다른 게 정상.
PUBLICATION_LAG_DAYS = 45


def _spread_band(value: Decimal) -> str:
    if value < 0:
        return "INVERTED"
    if value <= Decimal("0.5"):
        return "FLAT"
    return "NORMAL"


def _vix_band(value: Decimal) -> str:
    if value < 15:
        return "CALM"
    if value < 25:
        return "NORMAL"
    if value < 35:
        return "ELEVATED"
    return "CRISIS"


def _inflation_band(yoy: Decimal) -> str:
    if yoy < 0:
        return "DEFLATION"
    if yoy < 2:
        return "LOW"
    if yoy < 3:
        return "MODERATE"
    if yoy < 5:
        return "HIGH"
    return "VERY_HIGH"


_SPREAD_STRESS = {"INVERTED"}
_VIX_STRESS = {"ELEVATED", "CRISIS"}
_INFLATION_STRESS = {"HIGH", "VERY_HIGH", "DEFLATION"}


def load_series_csv(text: str) -> list[tuple[str, Decimal | None]]:
    """채널 표준 시계열 CSV(date,value — 빈 값은 결측) 파싱, 날짜 오름차순."""
    stripped = text.strip()
    if not stripped:
        raise ValueError("시계열 CSV 가 비어 있음")
    reader = csv.reader(io.StringIO(stripped))
    header = next(reader)
    if [h.strip().lower() for h in header[:2]] != ["date", "value"]:
        raise ValueError(f"시계열 CSV 헤더가 예상과 다름: {header!r}")
    out: list[tuple[str, Decimal | None]] = []
    for row in reader:
        if not row or not row[0].strip():
            continue
        raw = row[1].strip() if len(row) > 1 else ""
        try:
            value = None if raw == "" else Decimal(raw)
        except InvalidOperation as exc:
            raise ValueError(f"{row[0]}: 숫자가 아님 ({raw!r})") from exc
        out.append((row[0].strip(), value))
    out.sort(key=lambda p: p[0])
    return out


def _observed(points: list[tuple[str, Decimal | None]]) -> list[tuple[str, Decimal]]:
    return [(d, v) for d, v in points if v is not None]


def yield_curve_state(points: list[tuple[str, Decimal | None]]) -> dict[str, Any]:
    """10년-2년 스프레드 상태 + 최근 252 관측 중 역전 일수."""
    obs = _observed(points)
    if not obs:
        return {"status": "UNAVAILABLE", "reason": "관측 0개"}
    last_date, last = obs[-1]
    state = _spread_band(last)
    window = [v for _, v in obs[-252:]]
    return {
        "status": "OK",
        "state": state,
        "latest": str(last),
        "latest_date": last_date,
        "inverted_days_252": sum(1 for v in window if v < 0),
        "stress": state == "INVERTED",
    }


def vix_state(points: list[tuple[str, Decimal | None]]) -> dict[str, Any]:
    """VIX 수준 구간 + 전체 이력 백분위."""
    obs = _observed(points)
    if not obs:
        return {"status": "UNAVAILABLE", "reason": "관측 0개"}
    last_date, last = obs[-1]
    state = _vix_band(last)
    values = [v for _, v in obs]
    pct = Decimal(sum(1 for v in values if v <= last)) / Decimal(len(values)) * 100
    return {
        "status": "OK",
        "state": state,
        "latest": str(last),
        "latest_date": last_date,
        "history_percentile": f"{pct:.1f}",
        "history_obs": len(values),
        "stress": state in _VIX_STRESS,
    }


def inflation_state(points: list[tuple[str, Decimal | None]]) -> dict[str, Any]:
    """CPI 전년동월비. 12개월 전 같은 달 관측이 없으면(결측 포함) UNAVAILABLE."""
    obs = _observed(points)
    if not obs:
        return {"status": "UNAVAILABLE", "reason": "관측 0개"}
    last_date, last = obs[-1]
    y, m, _ = (int(x) for x in last_date.split("-"))
    base_date = f"{y - 1:04d}-{m:02d}-01"
    base = next((v for d, v in obs if d == base_date), None)
    if base is None or base == 0:
        return {
            "status": "UNAVAILABLE",
            "reason": f"12개월 전({base_date}) 관측 없음 — YoY 계산 불가",
        }
    yoy = (last / base - 1) * 100
    state = _inflation_band(yoy)
    return {
        "status": "OK",
        "state": state,
        "yoy_pct": f"{yoy:.2f}",
        "latest_date": last_date,
        "stress": state in _INFLATION_STRESS,
    }


def sahm_rule_state(points: list[tuple[str, Decimal | None]]) -> dict[str, Any]:
    """삼 룰: 실업률 3개월 이동평균 − 직전 12개월 내 3개월 이동평균 최솟값.

    결측 달(미발표 "-")은 건너뛰고 관측된 달의 연속 수열로 계산하되, 최소
    15개 관측(이동평균 3 + 되돌아보기 12)이 없으면 UNAVAILABLE. 표준 문턱
    0.5%p 이상이면 TRIGGERED(경기침체 신호).
    """
    obs = _observed(points)
    if len(obs) < 15:
        return {
            "status": "UNAVAILABLE",
            "reason": f"관측 {len(obs)}개 < 15개 (이동평균 3 + 되돌아보기 12)",
        }
    values = [v for _, v in obs]
    ma3 = [
        (values[i - 2] + values[i - 1] + values[i]) / 3 for i in range(2, len(values))
    ]
    current = ma3[-1]
    lookback = ma3[-13:-1]  # 직전 12개
    sahm = current - min(lookback)
    triggered = sahm >= SAHM_THRESHOLD
    return {
        "status": "OK",
        "state": "TRIGGERED" if triggered else "QUIET",
        "sahm_value_pp": f"{sahm:.2f}",
        "current_ma3": f"{current:.2f}",
        "latest_date": obs[-1][0],
        "stress": triggered,
    }


def compose_overall(indicators: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """스트레스 깃발 개수 → RISK_ON(0) / CAUTION(1) / RISK_OFF(>=2).

    계산 가능한 지표가 2개 미만이면 INSUFFICIENT — 깃발 0개를 안전으로
    오독하지 않는다(침묵은 성공이 아니다).
    """
    available = {k: v for k, v in indicators.items() if v.get("status") == "OK"}
    flags = sorted(k for k, v in available.items() if v.get("stress"))
    if len(available) < 2:
        label = "INSUFFICIENT"
    elif len(flags) >= 2:
        label = "RISK_OFF"
    elif len(flags) == 1:
        label = "CAUTION"
    else:
        label = "RISK_ON"
    return {
        "label": label,
        "stress_flags": flags,
        "available_indicators": len(available),
        "total_indicators": len(indicators),
        "note": "연구 전용 — 라이브 매매 신호 아님 (라이브 신호는 KIS 데이터만)",
    }


def build_macro_regime_report(data_dir: Path, *, as_of: date) -> dict[str, Any]:
    """발행 디렉터리의 CSV 들로 보고서 생성 — 지표 단위 fail-soft."""

    def _load(rel: str) -> list[tuple[str, Decimal | None]] | str:
        path = data_dir / rel
        if not path.is_file():
            return f"파일 없음: {rel} (해당 항목 미발행)"
        try:
            return load_series_csv(path.read_text(encoding="utf-8"))
        except ValueError as exc:
            return f"파싱 실패: {rel} — {exc}"

    indicators: dict[str, dict[str, Any]] = {}
    for key, rel, fn in (
        ("yield_curve", SPREAD_CSV, yield_curve_state),
        ("vix", VIX_CSV, vix_state),
        ("inflation", CPI_CSV, inflation_state),
        ("sahm", UNEMPLOYMENT_CSV, sahm_rule_state),
    ):
        loaded = _load(rel)
        if isinstance(loaded, str):
            indicators[key] = {"status": "UNAVAILABLE", "reason": loaded}
        else:
            indicators[key] = fn(loaded)
        indicators[key]["source"] = rel

    return {
        "schema_version": SCHEMA_VERSION,
        "as_of": as_of.isoformat(),
        "indicators": indicators,
        "overall": compose_overall(indicators),
    }


def report_to_json(report: dict[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2) + "\n"


# ---------------------------------------------------------------------------
# 이력 시계열 (타임라인) — 시점 기준(point-in-time) 일별 레짐 라벨
# ---------------------------------------------------------------------------


def _month_key(d: str) -> tuple[int, int]:
    y, m, _ = (int(x) for x in d.split("-"))
    return y, m


def _pit_monthly_states(
    cpi: list[tuple[str, Decimal]],
    unemployment: list[tuple[str, Decimal]],
    *,
    publication_lag_days: int,
) -> list[tuple[date, str | None, Decimal | None, str | None, Decimal | None]]:
    """월간 지표의 시점 기준 상태 변화점 목록.

    각 월 관측이 '발표(기준월 1일 + 지연일)'되는 날짜마다, 그 시점까지 발표된
    관측만으로 물가(YoY 구간)와 삼 룰 상태를 다시 계산한다. 반환은
    (발효일, 물가 상태, YoY, 삼 룰 상태, 삼 값) 의 시간순 목록 — 타임라인이
    날짜를 전진하며 포인터로 소비한다.
    """
    from datetime import timedelta

    events: list[tuple[date, str]] = []  # (발효일, 'cpi'|'une')
    for d, _ in cpi:
        y, m, dd = (int(x) for x in d.split("-"))
        events.append((date(y, m, dd) + timedelta(days=publication_lag_days), "cpi"))
    for d, _ in unemployment:
        y, m, dd = (int(x) for x in d.split("-"))
        events.append((date(y, m, dd) + timedelta(days=publication_lag_days), "une"))
    events.sort()

    cpi_by_month = {_month_key(d): v for d, v in cpi}
    cpi_sorted = sorted(cpi, key=lambda p: p[0])
    une_sorted = sorted(unemployment, key=lambda p: p[0])

    out: list[tuple[date, str | None, Decimal | None, str | None, Decimal | None]] = []
    n_cpi = n_une = 0
    for effective, kind in events:
        if kind == "cpi":
            n_cpi += 1
        else:
            n_une += 1
        # 물가: 발표분 중 최신 달의 YoY (12개월 전 달 필요)
        infl_state: str | None = None
        yoy: Decimal | None = None
        if n_cpi:
            last_d, last_v = cpi_sorted[n_cpi - 1]
            y, m = _month_key(last_d)
            base = cpi_by_month.get((y - 1, m))
            if base:
                yoy = (last_v / base - 1) * 100
                infl_state = _inflation_band(yoy)
        # 삼 룰: 발표분 관측 15개 이상일 때
        sahm_state: str | None = None
        sahm_val: Decimal | None = None
        if n_une >= 15:
            values = [v for _, v in une_sorted[:n_une]]
            ma3 = [
                (values[i - 2] + values[i - 1] + values[i]) / 3
                for i in range(2, len(values))
            ]
            sahm_val = ma3[-1] - min(ma3[-13:-1])
            sahm_state = "TRIGGERED" if sahm_val >= SAHM_THRESHOLD else "QUIET"
        out.append((effective, infl_state, yoy, sahm_state, sahm_val))
    return out


def daily_regime_timeline(
    spread: list[tuple[str, Decimal | None]],
    vix: list[tuple[str, Decimal | None]],
    cpi: list[tuple[str, Decimal | None]],
    unemployment: list[tuple[str, Decimal | None]],
    *,
    publication_lag_days: int = PUBLICATION_LAG_DAYS,
) -> list[dict[str, Any]]:
    """일별 레짐 라벨 이력 — 백테스트 층화 분석용 (연구 전용).

    시점 기준 규칙(미래 정보 누출 차단):
      * 일간 지표(금리차·VIX)는 그날 종가 — 라벨은 "그날 장 마감 시점의 레짐".
        d일 라벨로 층화할 수익률은 d일 *이후*의 것이어야 한다(소비자 책임,
        regime_stratified 가 이 규칙대로 d+1 수익률을 붙인다).
      * 월간 지표(CPI·실업률)는 기준월 1일 + 발표 지연(기본 45일)부터 반영 —
        최신 스냅숏(regime.json)과 마지막 구간이 다를 수 있는 게 정상이다.

    날짜 축은 금리차∩VIX 공통 영업일. 라벨 규칙은 스냅숏과 동일(깃발 수
    0/1/>=2 → RISK_ON/CAUTION/RISK_OFF, 가용 지표 <2 → INSUFFICIENT).
    """
    spread_by_date = {d: v for d, v in spread if v is not None}
    vix_by_date = {d: v for d, v in vix if v is not None}
    days = sorted(set(spread_by_date) & set(vix_by_date))

    monthly = _pit_monthly_states(
        _observed(cpi), _observed(unemployment), publication_lag_days=publication_lag_days
    )
    m_idx = 0
    infl_state: str | None = None
    yoy: Decimal | None = None
    sahm_state: str | None = None
    sahm_val: Decimal | None = None

    rows: list[dict[str, Any]] = []
    for d in days:
        d_date = date.fromisoformat(d)
        while m_idx < len(monthly) and monthly[m_idx][0] <= d_date:
            _, infl_state, yoy, sahm_state, sahm_val = monthly[m_idx]
            m_idx += 1
        s_band = _spread_band(spread_by_date[d])
        v_band = _vix_band(vix_by_date[d])
        flags = []
        if s_band in _SPREAD_STRESS:
            flags.append("yield_curve")
        if v_band in _VIX_STRESS:
            flags.append("vix")
        if infl_state in _INFLATION_STRESS:
            flags.append("inflation")
        if sahm_state == "TRIGGERED":
            flags.append("sahm")
        available = 2 + (infl_state is not None) + (sahm_state is not None)
        if available < 2:  # pragma: no cover - 날짜 축 정의상 항상 >=2
            label = "INSUFFICIENT"
        elif len(flags) >= 2:
            label = "RISK_OFF"
        elif len(flags) == 1:
            label = "CAUTION"
        else:
            label = "RISK_ON"
        rows.append(
            {
                "date": d,
                "label": label,
                "flags": ";".join(flags),
                "available": available,
                "spread": str(spread_by_date[d]),
                "vix": str(vix_by_date[d]),
                "inflation_yoy": "" if yoy is None else f"{yoy:.2f}",
                "sahm_pp": "" if sahm_val is None else f"{sahm_val:.2f}",
            }
        )
    return rows


def timeline_to_csv(rows: list[dict[str, Any]]) -> str:
    out = io.StringIO()
    fields = [
        "date", "label", "flags", "available", "spread", "vix",
        "inflation_yoy", "sahm_pp",
    ]
    writer = csv.DictWriter(out, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue()


def build_regime_timeline(
    data_dir: Path, *, publication_lag_days: int = PUBLICATION_LAG_DAYS
) -> list[dict[str, Any]]:
    """발행 디렉터리의 CSV 들로 타임라인 생성. 일간 축(금리차·VIX) 없으면 빈 목록."""

    def _load(rel: str) -> list[tuple[str, Decimal | None]]:
        path = data_dir / rel
        if not path.is_file():
            return []
        try:
            return load_series_csv(path.read_text(encoding="utf-8"))
        except ValueError:
            return []

    return daily_regime_timeline(
        _load(SPREAD_CSV),
        _load(VIX_CSV),
        _load(CPI_CSV),
        _load(UNEMPLOYMENT_CSV),
        publication_lag_days=publication_lag_days,
    )
