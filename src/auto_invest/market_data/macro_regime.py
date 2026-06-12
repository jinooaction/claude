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
    if last < 0:
        state = "INVERTED"
    elif last <= Decimal("0.5"):
        state = "FLAT"
    else:
        state = "NORMAL"
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
    if last < 15:
        state = "CALM"
    elif last < 25:
        state = "NORMAL"
    elif last < 35:
        state = "ELEVATED"
    else:
        state = "CRISIS"
    values = [v for _, v in obs]
    pct = Decimal(sum(1 for v in values if v <= last)) / Decimal(len(values)) * 100
    return {
        "status": "OK",
        "state": state,
        "latest": str(last),
        "latest_date": last_date,
        "history_percentile": f"{pct:.1f}",
        "history_obs": len(values),
        "stress": state in ("ELEVATED", "CRISIS"),
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
    if yoy < 0:
        state = "DEFLATION"
    elif yoy < 2:
        state = "LOW"
    elif yoy < 3:
        state = "MODERATE"
    elif yoy < 5:
        state = "HIGH"
    else:
        state = "VERY_HIGH"
    return {
        "status": "OK",
        "state": state,
        "yoy_pct": f"{yoy:.2f}",
        "latest_date": last_date,
        "stress": state in ("HIGH", "VERY_HIGH", "DEFLATION"),
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
