# HANDOFF 032 — 스펙 023: 가격 기반 퀄리티 팩터 필터 (2026-05-29)

## 한 줄 요약

KIS API 재무 데이터 없이 순수 가격 시계열로 퀄리티를 측정하는
`QualityFilter(top_n/top_pct)` 옵트인 필터를 추가했습니다.
PR #100 머지 커밋 `674c8dc`. 신규 테스트 8건, 전체 1195 통과, 린트 깨끗.

## 배경 — 세계 최고 수준 격차 분석

스펙 022(최소 분산)에 이어 다음 격차로 **퀄리티 팩터**를 선택했습니다.
KIS API로 ROE·이익률 같은 재무 데이터를 가져오는 경로가 없으므로
가격 시계열만으로 퀄리티를 근사했습니다.

| 레이어 | 기존 | 스펙 023 후 |
|--------|------|------------|
| 시계열 모멘텀 | ✅ 스펙 018 | ✅ |
| 횡단면 모멘텀 순위 | ✅ 스펙 021 | ✅ |
| ERC 등기여 위험 | ✅ 스펙 019 | ✅ |
| 최소 분산 최적화 | ✅ 스펙 022 | ✅ |
| 퀄리티 팩터 필터 | ❌ | ✅ `QualityFilter` |
| 레짐 필터 | ✅ 스펙 020 | ✅ |

**퀄리티 점수** = 롤링 샤프 비율 / (1 + |최대 드로다운 비율|)

- 롤링 샤프: `annualised(mean(log_r) / std(log_r))` — 수익 대비 변동성 효율
- 최대 드로다운 비율: `(peak − trough) / peak` — 손실 내성

## 변경 사항

### `strategy/quality.py` (신규, 비커널)

- `price_quality_score(bars, *, lookback_bars, annualise_factor)`:
  - 로그 수익률로 롤링 샤프 계산.
  - 최대 드로다운 비율 계산.
  - 합성 점수 = sharpe / (1 + abs(max_dd)).
  - 데이터 부족(< 30봉) → `Decimal("-Inf")` (항상 하위 랭크).
  - Decimal 6자리 반올림.
- `quality_ranked(symbol_bars, *, lookback_bars)`:
  - 유니버스 전체를 점수로 내림차순 정렬.
  - 동점 시 심볼명 알파벳 순 (결정론적).

### `config/rules.py` (비커널)

- `_MIN_QUALITY_BARS = 30` 상수.
- `QualityFilter` Pydantic 모델:
  - `universe: tuple[str, ...]` — 순위 매길 심볼 목록 (2개 이상).
  - `lookback_bars: int = 60` — 퀄리티 측정 기간.
  - `top_n: int | None` — 상위 N개만 통과.
  - `top_pct: float | None` — 상위 P% 이내만 통과.
  - `top_n`과 `top_pct` 중 정확히 하나만 설정 (검증).
  - `.qualifies(symbol, ranked)` 헬퍼.
- `TradingRule.quality_filter: QualityFilter | None = None` 옵트인 필드.

### `execution/order_router.py` (비커널)

- `quality_ranked` import 추가.
- 랭킹 필터(스펙 021) 이후, 판단 자문(스펙 004) 이전에 퀄리티 필터 분기.
- 미통과 → `OrderOutcome(state="SKIPPED_BY_QUALITY", reason="not_in_top_quality")`.

### `backtest/replay.py` (비커널)

- 동일 패턴. `session_date` 이하 바만 사용(미래 참조 없음).

## 안전 경계

- **Kernel 터치 0건**: `risk/gates.py`(K1) 변경 없음.
- **하향 전용**: 주문을 건너뛸 뿐 수량을 올리지 않음 — K1 불변.
- **옵트인**: `quality_filter=None` 기본값, 기존 룰 byte 동일.
- **결정론적**: Decimal 출력, 백테스트=라이브 단일 잣대(헌법 X.2).
- `AUTO_INVEST_MODE=live` 전환 미포함 — 운영자 명시 지시 필요.

## 테스트 (`tests/unit/test_spec_023_quality_factor.py`) — 8개

- SC-01: 안정적 상승 종목이 변동성 높은 종목보다 높은 퀄리티 점수
- SC-02: 데이터 부족(< 30봉) → `Decimal("-Inf")`
- SC-03: 드로다운 없는 종목 > 드로다운 큰 종목 점수
- SC-04: `quality_ranked` 내림차순 정렬 검증
- SC-05: `QualityFilter.qualifies` top_n 동작
- SC-06: `QualityFilter.qualifies` top_pct 동작
- SC-07: `quality_filter=None` 옵트인 검증
- SC-08: `top_n`/`top_pct` 동시 설정 → `ValidationError`

전체 1195 통과, 4 스킵(KIS smoke), 린트 깨끗.

## 실거래 전환 가능성 (이 세션 평가)

| 항목 | 상태 |
|------|------|
| K1 포지션 한도 | ✅ |
| 손실 서킷 브레이커(스펙 014) | ✅ |
| 체결 동기화(스펙 015) | ✅ |
| 일일 정합성(스펙 001) | ✅ |
| 하드닝 캐너리(스펙 007) 합성 데이터 통과 | ✅ (이 세션, CANARY_PASSED 감사 기록) |
| 실서버 캐너리(Vultr + KIS 시크릿) | ❌ **블로커** |
| 페이퍼 트레이딩 실적 | ⚠️ 컨테이너에서 접근 불가 |

**결론**: 아키텍처 준비 완료. 헌법 VI조(Backtest→Canary→Full Live)에 따라
실서버(Vultr)에서 KIS 시크릿으로 캐너리 1단계를 실행해야 실거래 2단계로 진입 가능.
운영자 "캐너리 시작해줘(Vultr에서)" 지시 시 즉시 실행 가능.

## 다음 후보

1. **기대 수익률 모델 + 최대 샤프 (스펙 024 후보)** — 모멘텀 신호를 기대 수익률로 활용,
   평균-분산 전선에서 최대 샤프 포인트 직접 최적화.
2. **실거래 캐너리** — Vultr 서버에서 KIS 시크릿으로 `AUTO_INVEST_MODE=live` 전환.
   **운영자 명시 지시 필요.**
3. **퀄리티 팩터 고도화** — 재무 데이터 API가 확보되면 ROE·이익률 기반으로 교체.
