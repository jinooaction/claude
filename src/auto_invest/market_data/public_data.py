"""공개 데이터 수집 채널 (세계 최고 수준 4단계 계획 ④ — 연구 전용).

운영자 승인(2026-06-11): Stooq(일봉 OHLCV) + FRED(거시 CSV) 두 소스.
컨테이너는 GitHub 만 닿지만 GitHub Actions 실행기는 인터넷 전체에 닿으므로,
수집은 `.github/workflows/collect-public-data.yml` 이 실행기에서 돌리고 결과를
`automation/public-data` 사이드카 브랜치로 발행한다.

격리 원칙(안전 경계 아님 — 데이터 신뢰 경계):
  * 라이브 매매 신호는 계속 KIS 데이터(`price_bars`)만 사용한다. 이 채널의
    산출물은 연구·백테스트·검증 전용이며 라이브 DB 에 절대 쓰지 않는다.
  * 검증을 통과한 항목만 발행한다(실패 슬리브만 제외하는 fail-soft —
    ARM F 백필과 같은 원칙). 모든 항목의 합격/불합격은 summary 에 남는다.
  * 두 소스 교차 검증(SPY 일일 수익률 vs FRED SP500 지수 수익률)으로
    단일 소스 오염을 잡는다. KIS 와의 대조는 KIS DB 가 있는 곳(서버/세션)에서
    `cross_check_daily_returns` 를 재사용해 수행한다.

추가 라이브러리 0개 — 표준 httpx 만 사용(공급망 무변경).
"""

from __future__ import annotations

import csv
import io
import json
import time
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import httpx

STOOQ_BASE = "https://stooq.com/q/d/l/"
FRED_BASE = "https://fred.stlouisfed.org/graph/fredgraph.csv"

# 실행기에서 공개 엔드포인트를 부를 때의 식별 헤더(차단 회피용 위장 아님 —
# 정직한 자기 식별. 봇 차단 정책 변경은 검증 단계가 형식 오류로 잡는다).
USER_AGENT = "auto-invest-research/1.0 (public-data channel)"


@dataclass(frozen=True)
class PublicBar:
    """공개 소스 일봉(연구 전용 — KIS `PriceBar` 와 의도적으로 별개 타입).

    별개 타입인 이유: 라이브 신호 경로(`store.PriceBar`)와 타입 수준에서
    섞이지 않게 해 "연구 데이터가 실수로 라이브 DB 에 들어가는" 실수를
    코드 리뷰 없이도 어렵게 만든다.
    """

    date: str  # YYYY-MM-DD
    open_usd: Decimal
    high_usd: Decimal
    low_usd: Decimal
    close_usd: Decimal
    volume: int


@dataclass(frozen=True)
class SeriesPoint:
    """FRED 시계열 한 점. value=None 은 결측("." 표기)."""

    date: str  # YYYY-MM-DD
    value: Decimal | None


@dataclass(frozen=True)
class Validation:
    """단일 항목(심볼/시리즈) 검증 결과. ok=False 항목은 발행하지 않는다."""

    ok: bool
    rows: int
    first_date: str | None
    last_date: str | None
    issues: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CrossCheck:
    """두 소스 일일 수익률 교차 검증 결과."""

    status: str  # PASS | FAIL | INSUFFICIENT_OVERLAP
    overlap_returns: int
    agree_pct: str | None  # Decimal 문자열(JSON 안전)
    max_abs_diff_pct: str | None
    detail: str


def stooq_daily_csv_url(symbol: str, *, default_suffix: str = ".us") -> str:
    """Stooq 일봉 CSV 주소. 접미사 없는 심볼은 미국 시장(.us)으로 본다."""
    s = symbol.strip().lower()
    if not s:
        raise ValueError("empty symbol")
    if "." not in s and not s.startswith("^"):
        s += default_suffix
    return f"{STOOQ_BASE}?s={s}&i=d"


def fred_csv_url(series_id: str) -> str:
    """FRED fredgraph CSV 주소(키 불필요 공개 엔드포인트)."""
    sid = series_id.strip().upper()
    if not sid:
        raise ValueError("empty series id")
    return f"{FRED_BASE}?id={sid}"


def _parse_decimal(raw: str, *, what: str) -> Decimal:
    try:
        return Decimal(raw)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{what}: 숫자가 아님 ({raw!r})") from exc


def parse_stooq_daily_csv(text: str) -> list[PublicBar]:
    """Stooq 일봉 CSV(Date,Open,High,Low,Close,Volume) 파싱.

    형식이 다르면(차단 페이지·"No data"·HTML 등) ValueError — 조용히 빈 목록을
    내지 않는다(소스 형식 변경을 검증 실패로 드러내는 게 채널의 일).
    날짜 오름차순으로 정렬해 돌려준다.
    """
    stripped = text.strip()
    if not stripped or stripped.lower().startswith("no data"):
        raise ValueError("Stooq 응답에 데이터 없음 ('No data' 또는 빈 본문)")
    reader = csv.reader(io.StringIO(stripped))
    try:
        header = next(reader)
    except StopIteration as exc:  # pragma: no cover - stripped 가 비면 위에서 걸림
        raise ValueError("Stooq 응답이 비어 있음") from exc
    expected = ["Date", "Open", "High", "Low", "Close"]
    if [h.strip() for h in header[:5]] != expected:
        raise ValueError(f"Stooq CSV 헤더가 예상과 다름: {header!r}")
    bars: list[PublicBar] = []
    for row in reader:
        if not row or not row[0].strip():
            continue
        if len(row) < 5:
            raise ValueError(f"Stooq CSV 행 필드 부족: {row!r}")
        d = row[0].strip()
        # 거래량은 일부 지수/통화에서 비어 있을 수 있음 → 0 으로 본다.
        vol_raw = row[5].strip() if len(row) > 5 and row[5].strip() else "0"
        try:
            volume = int(Decimal(vol_raw))
        except (InvalidOperation, ValueError) as exc:
            raise ValueError(f"{d}: 거래량이 숫자가 아님 ({vol_raw!r})") from exc
        bars.append(
            PublicBar(
                date=d,
                open_usd=_parse_decimal(row[1].strip(), what=f"{d} open"),
                high_usd=_parse_decimal(row[2].strip(), what=f"{d} high"),
                low_usd=_parse_decimal(row[3].strip(), what=f"{d} low"),
                close_usd=_parse_decimal(row[4].strip(), what=f"{d} close"),
                volume=volume,
            )
        )
    bars.sort(key=lambda b: b.date)
    return bars


def parse_fred_csv(text: str) -> list[SeriesPoint]:
    """FRED fredgraph CSV 파싱. 헤더는 (DATE|observation_date),<SERIES_ID>.

    결측값 "." 은 value=None 으로 보존한다(스킵하면 결측률을 검증할 수 없다).
    """
    stripped = text.strip()
    if not stripped:
        raise ValueError("FRED 응답이 비어 있음")
    reader = csv.reader(io.StringIO(stripped))
    try:
        header = next(reader)
    except StopIteration as exc:  # pragma: no cover
        raise ValueError("FRED 응답이 비어 있음") from exc
    if len(header) < 2 or header[0].strip().lower() not in ("date", "observation_date"):
        raise ValueError(f"FRED CSV 헤더가 예상과 다름: {header!r}")
    points: list[SeriesPoint] = []
    for row in reader:
        if not row or not row[0].strip():
            continue
        if len(row) < 2:
            raise ValueError(f"FRED CSV 행 필드 부족: {row!r}")
        d = row[0].strip()
        raw = row[1].strip()
        value = None if raw in (".", "") else _parse_decimal(raw, what=f"{d} value")
        points.append(SeriesPoint(date=d, value=value))
    points.sort(key=lambda p: p.date)
    return points


def _iso(d: str) -> date:
    return date.fromisoformat(d)


def validate_daily_bars(
    bars: list[PublicBar],
    *,
    as_of: date,
    min_rows: int = 250,
    max_staleness_days: int = 7,
    max_gap_days: int = 10,
    max_day_move_pct: Decimal = Decimal("40"),
) -> Validation:
    """일봉 품질 검증 — 통과 못 하면 발행하지 않는다.

    검사: 행 수(연구에 쓸 만큼 깊은가) / 날짜 중복·역순 / OHLC 정합(양수,
    high≥max(o,c), low≤min(o,c)) / 일일 변동 이상치(|수익률| > max_day_move_pct)
    / 신선도(마지막 봉이 as_of 기준 max_staleness_days 이내) / 연속성(달력일
    기준 max_gap_days 초과 공백 없음).
    """
    issues: list[str] = []
    rows = len(bars)
    first = bars[0].date if bars else None
    last = bars[-1].date if bars else None
    if rows < min_rows:
        issues.append(f"행 부족: {rows} < 최소 {min_rows}")
    prev: PublicBar | None = None
    for b in bars:
        if min(b.open_usd, b.high_usd, b.low_usd, b.close_usd) <= 0:
            issues.append(f"{b.date}: 0 이하 가격")
        if b.high_usd < max(b.open_usd, b.close_usd) or b.low_usd > min(
            b.open_usd, b.close_usd
        ):
            issues.append(f"{b.date}: OHLC 정합 위반")
        if b.volume < 0:
            issues.append(f"{b.date}: 음수 거래량")
        if prev is not None:
            if b.date <= prev.date:
                issues.append(f"{b.date}: 날짜 중복/역순 (이전 {prev.date})")
            else:
                gap = (_iso(b.date) - _iso(prev.date)).days
                if gap > max_gap_days:
                    issues.append(f"{prev.date}→{b.date}: {gap}일 공백 > {max_gap_days}")
            if prev.close_usd > 0:
                move = abs(b.close_usd / prev.close_usd - 1) * 100
                if move > max_day_move_pct:
                    issues.append(
                        f"{b.date}: 일일 변동 {move:.1f}% > {max_day_move_pct}% (이상치)"
                    )
        prev = b
        if len(issues) >= 20:  # 진단 폭주 방지 — 처음 20건이면 원인 파악에 충분
            issues.append("(이후 생략)")
            break
    if last is not None:
        staleness = (as_of - _iso(last)).days
        if staleness > max_staleness_days:
            issues.append(f"신선도 위반: 마지막 봉 {last} 이 {staleness}일 전")
    return Validation(ok=not issues, rows=rows, first_date=first, last_date=last, issues=issues)


def validate_series(
    points: list[SeriesPoint],
    *,
    as_of: date,
    min_rows: int = 24,
    max_staleness_days: int = 70,
) -> Validation:
    """FRED 시계열 검증. 월간 시리즈(CPI 등)는 발표가 ~45일 늦으므로
    신선도 기본값을 70일로 느슨하게 둔다(이 검사는 '피드가 살아있나' 수준)."""
    issues: list[str] = []
    rows = len(points)
    first = points[0].date if points else None
    last_observed = next((p.date for p in reversed(points) if p.value is not None), None)
    if rows < min_rows:
        issues.append(f"행 부족: {rows} < 최소 {min_rows}")
    seen: str | None = None
    for p in points:
        if seen is not None and p.date <= seen:
            issues.append(f"{p.date}: 날짜 중복/역순 (이전 {seen})")
            break
        seen = p.date
    if last_observed is None:
        issues.append("관측값 전부 결측")
    else:
        staleness = (as_of - _iso(last_observed)).days
        if staleness > max_staleness_days:
            issues.append(f"신선도 위반: 마지막 관측 {last_observed} 이 {staleness}일 전")
    return Validation(
        ok=not issues,
        rows=rows,
        first_date=first,
        last_date=last_observed,
        issues=issues,
    )


def cross_check_daily_returns(
    closes_a: dict[str, Decimal],
    closes_b: dict[str, Decimal],
    *,
    tolerance_pct: Decimal = Decimal("0.5"),
    min_overlap_returns: int = 60,
    min_agree_pct: Decimal = Decimal("95"),
) -> CrossCheck:
    """두 소스의 *일일 수익률* 을 겹치는 날짜에서 대조한다.

    수준(레벨)이 아니라 수익률을 비교하는 이유: 배당/분할 조정 방식이 소스마다
    달라 레벨은 정당하게 어긋날 수 있지만, 일일 수익률은 조정 방식과 거의
    무관하다(배당락일 등 소수 날짜만 어긋남 → min_agree_pct 로 흡수).
    KIS `price_bars` 종가와의 대조에도 이 함수를 그대로 쓴다.
    """
    common = sorted(set(closes_a) & set(closes_b))
    diffs: list[Decimal] = []
    for prev_d, cur_d in zip(common, common[1:], strict=False):
        pa, ca = closes_a[prev_d], closes_a[cur_d]
        pb, cb = closes_b[prev_d], closes_b[cur_d]
        if min(pa, pb) <= 0:
            continue
        ra = (ca / pa - 1) * 100
        rb = (cb / pb - 1) * 100
        diffs.append(abs(ra - rb))
    if len(diffs) < min_overlap_returns:
        return CrossCheck(
            status="INSUFFICIENT_OVERLAP",
            overlap_returns=len(diffs),
            agree_pct=None,
            max_abs_diff_pct=None,
            detail=f"겹치는 수익률 {len(diffs)}개 < 최소 {min_overlap_returns}개",
        )
    agree = sum(1 for d in diffs if d <= tolerance_pct)
    agree_pct = Decimal(agree) / Decimal(len(diffs)) * 100
    max_diff = max(diffs)
    status = "PASS" if agree_pct >= min_agree_pct else "FAIL"
    return CrossCheck(
        status=status,
        overlap_returns=len(diffs),
        agree_pct=f"{agree_pct:.2f}",
        max_abs_diff_pct=f"{max_diff:.4f}",
        detail=(
            f"일치 {agree}/{len(diffs)} ({agree_pct:.2f}%) — 허용 오차 "
            f"±{tolerance_pct}%p, 합격선 {min_agree_pct}%"
        ),
    )


def fetch_text(
    client: httpx.Client,
    url: str,
    *,
    max_retries: int = 3,
    timeout: float | None = None,
) -> str:
    """공개 CSV 한 건을 받아온다. 5xx/네트워크 오류는 지수 백오프로 재시도.

    ``timeout`` 이 주어지면 요청 단위로 클라이언트 기본값을 덮어쓴다 —
    배치 수집에서는 짧게(15초) 잡아 타르핏(연결 후 무응답)이 전체 시간
    예산을 잡아먹지 못하게 한다(2026-06-11 첫 실측: FRED 가 실행기 IP 에
    30초 무응답 × 재시도 4회 × 7시리즈 ≈ 15분 → 작업 제한 초과).
    """
    delay = 1.0
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            kwargs: dict[str, Any] = {"headers": {"User-Agent": USER_AGENT}}
            if timeout is not None:
                kwargs["timeout"] = timeout
            resp = client.get(url, **kwargs)
            if resp.status_code >= 500:
                raise httpx.HTTPStatusError(
                    f"server error {resp.status_code}", request=resp.request, response=resp
                )
            resp.raise_for_status()
            return resp.text
        except (httpx.TransportError, httpx.HTTPStatusError) as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            if status is not None and 400 <= status < 500:
                raise  # 4xx 는 재시도 무의미(주소/심볼 문제) — 즉시 드러낸다.
            last_exc = exc
            if attempt < max_retries:
                time.sleep(delay)
                delay *= 2
    raise last_exc if last_exc else RuntimeError("unreachable")


def probe_url(
    client: httpx.Client,
    url: str,
    *,
    user_agent: str | None,
    timeout: float = 10.0,
    max_bytes: int = 240,
) -> dict[str, Any]:
    """소스 경로 탐침 — 상태 코드·지연·첫 바이트만 기록하고 끊는다.

    2026-06-11 첫 실측이 두 소스 모두 실행기에서 막힘(Stooq=JS 봇 장벽,
    FRED=타르핏)을 드러냈다. 매 런이 측정 장비가 되도록 후보 경로를 가볍게
    두드려 summary 에 남긴다 — 어떤 경로/UA 가 통하는지의 증거가 쌓인다.
    수 KB 만 읽고 스트림을 닫으므로 대용량(벌크 zip)도 안전하다.
    """
    headers = {"User-Agent": user_agent} if user_agent else {}
    start = time.monotonic()
    out: dict[str, Any] = {
        "url": url,
        "user_agent": "channel" if user_agent else "httpx-default",
    }
    try:
        with client.stream("GET", url, headers=headers, timeout=timeout) as resp:
            head = b""
            for chunk in resp.iter_bytes():
                head += chunk
                if len(head) >= max_bytes:
                    break
            printable = head[:max_bytes].decode("utf-8", errors="replace")
            printable = "".join(ch if ch.isprintable() else "·" for ch in printable)
            out.update(
                status=resp.status_code,
                ok=resp.status_code == 200,
                elapsed_ms=int((time.monotonic() - start) * 1000),
                content_head=printable[:200],
            )
    except Exception as exc:  # noqa: BLE001 — 탐침은 절대 수집을 깨지 않는다
        out.update(
            status=None,
            ok=False,
            elapsed_ms=int((time.monotonic() - start) * 1000),
            error=f"{type(exc).__name__}: {exc}",
        )
    return out


def _bars_to_csv(bars: list[PublicBar]) -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(["date", "open", "high", "low", "close", "volume"])
    for b in bars:
        writer.writerow(
            [b.date, str(b.open_usd), str(b.high_usd), str(b.low_usd), str(b.close_usd), b.volume]
        )
    return out.getvalue()


def _series_to_csv(points: list[SeriesPoint]) -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(["date", "value"])
    for p in points:
        writer.writerow([p.date, "" if p.value is None else str(p.value)])
    return out.getvalue()


def collect_public_data(
    client: httpx.Client,
    config: dict[str, Any],
    *,
    out_dir: Path,
    as_of: date,
) -> dict[str, Any]:
    """수집 → 검증 → 통과분만 ``out_dir`` 에 발행, 전 항목 요약을 돌려준다.

    fail-soft: 항목 하나의 실패(차단·형식 변경·신선도 위반)는 그 항목만
    미발행으로 남기고 나머지는 계속한다. 모든 항목이 실패하면 overall_ok=False
    에 published=0 — 워크플로가 빨간 신호로 올린다.
    """
    stooq_cfg = config.get("stooq", {})
    fred_cfg = config.get("fred", {})
    cross_cfg = config.get("cross_check", {})
    coll_cfg = config.get("collection", {})

    # 시간 예산 — 타르핏(연결 후 무응답)이 워크플로 작업 제한(15분)을 잡아먹어
    # 발행 스텝까지 죽는 일이 없게, 수집 전체에 벽시계 상한을 둔다. 예산 초과
    # 시점 이후의 항목은 "미시도"로 기록하고 즉시 요약 발행으로 넘어간다.
    request_timeout = float(coll_cfg.get("request_timeout_seconds", 15))
    max_retries = int(coll_cfg.get("max_retries", 1))
    time_budget = float(coll_cfg.get("time_budget_seconds", 480))
    started = time.monotonic()

    def _over_budget() -> bool:
        return time.monotonic() - started > time_budget

    # 탐침은 수집보다 먼저 — 소스가 전멸한 날에도 진단 증거는 반드시 남는다.
    probes: list[dict[str, Any]] = []
    for url in config.get("probes", {}).get("urls", []):
        for ua in (USER_AGENT, None):
            if _over_budget():
                break
            probes.append(
                probe_url(client, url, user_agent=ua, timeout=min(request_timeout, 10.0))
            )

    items: list[dict[str, Any]] = []
    closes_by_symbol: dict[str, dict[str, Decimal]] = {}
    series_by_id: dict[str, dict[str, Decimal]] = {}

    for symbol in stooq_cfg.get("symbols", []):
        item: dict[str, Any] = {"kind": "stooq", "id": symbol}
        if _over_budget():
            item.update(ok=False, issues=[f"시간 예산({int(time_budget)}초) 초과 — 미시도"])
            items.append(item)
            continue
        try:
            text = fetch_text(
                client,
                stooq_daily_csv_url(symbol),
                max_retries=max_retries,
                timeout=request_timeout,
            )
            bars = parse_stooq_daily_csv(text)
            v = validate_daily_bars(
                bars,
                as_of=as_of,
                min_rows=int(stooq_cfg.get("min_rows", 250)),
                max_staleness_days=int(stooq_cfg.get("max_staleness_days", 7)),
            )
            item.update(
                ok=v.ok, rows=v.rows, first_date=v.first_date, last_date=v.last_date,
                issues=v.issues,
            )
            if v.ok:
                path = out_dir / "stooq" / f"{symbol.upper()}.csv"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(_bars_to_csv(bars), encoding="utf-8")
                item["published"] = str(path.relative_to(out_dir))
                closes_by_symbol[symbol.upper()] = {b.date: b.close_usd for b in bars}
        except Exception as exc:  # noqa: BLE001 — 항목 단위 fail-soft 가 채널의 계약
            item.update(ok=False, issues=[f"{type(exc).__name__}: {exc}"])
        items.append(item)

    for series_id in fred_cfg.get("series", []):
        item = {"kind": "fred", "id": series_id}
        if _over_budget():
            item.update(ok=False, issues=[f"시간 예산({int(time_budget)}초) 초과 — 미시도"])
            items.append(item)
            continue
        try:
            text = fetch_text(
                client,
                fred_csv_url(series_id),
                max_retries=max_retries,
                timeout=request_timeout,
            )
            points = parse_fred_csv(text)
            v = validate_series(
                points,
                as_of=as_of,
                min_rows=int(fred_cfg.get("min_rows", 24)),
                max_staleness_days=int(fred_cfg.get("max_staleness_days", 70)),
            )
            missing = sum(1 for p in points if p.value is None)
            item.update(
                ok=v.ok, rows=v.rows, first_date=v.first_date, last_date=v.last_date,
                missing=missing, issues=v.issues,
            )
            if v.ok:
                path = out_dir / "fred" / f"{series_id.upper()}.csv"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(_series_to_csv(points), encoding="utf-8")
                item["published"] = str(path.relative_to(out_dir))
                series_by_id[series_id.upper()] = {
                    p.date: p.value for p in points if p.value is not None
                }
        except Exception as exc:  # noqa: BLE001 — 항목 단위 fail-soft
            item.update(ok=False, issues=[f"{type(exc).__name__}: {exc}"])
        items.append(item)

    # 두 소스 교차 검증 — 단일 소스 오염(조용한 데이터 변질)을 잡는 핵심 게이트.
    cross: dict[str, Any] | None = None
    cc_symbol = str(cross_cfg.get("stooq_symbol", "")).upper()
    cc_series = str(cross_cfg.get("fred_series", "")).upper()
    if cc_symbol and cc_series:
        a = closes_by_symbol.get(cc_symbol)
        b = series_by_id.get(cc_series)
        if a is None or b is None:
            cross = {
                "status": "SKIPPED",
                "detail": f"교차 검증 입력 미발행 (stooq {cc_symbol}: "
                f"{'있음' if a else '없음'}, fred {cc_series}: {'있음' if b else '없음'})",
            }
        else:
            cc = cross_check_daily_returns(
                a,
                b,
                tolerance_pct=Decimal(str(cross_cfg.get("tolerance_pct", "0.5"))),
                min_overlap_returns=int(cross_cfg.get("min_overlap_returns", 60)),
                min_agree_pct=Decimal(str(cross_cfg.get("min_agree_pct", "95"))),
            )
            cross = {
                "status": cc.status,
                "pair": f"{cc_symbol} vs {cc_series}",
                "overlap_returns": cc.overlap_returns,
                "agree_pct": cc.agree_pct,
                "max_abs_diff_pct": cc.max_abs_diff_pct,
                "detail": cc.detail,
            }

    published = sum(1 for i in items if i.get("published"))
    overall_ok = (
        published > 0
        and all(i["ok"] for i in items)
        and (cross is None or cross["status"] == "PASS")
    )
    summary: dict[str, Any] = {
        "schema_version": "1.1",
        "as_of": as_of.isoformat(),
        "overall_ok": overall_ok,
        "published": published,
        "total_items": len(items),
        "elapsed_seconds": round(time.monotonic() - started, 1),
        "cross_check": cross,
        "probes": probes,
        "items": items,
        "isolation_note": "연구 전용 — 라이브 매매 신호는 KIS 데이터만 사용",
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return summary
