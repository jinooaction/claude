# HANDOFF 030 — 스펙 021: 횡단면 모멘텀 순위 필터 (2026-05-29)

## 한 줄 요약

전체 유니버스를 N-기간 수익률로 순위 매겨 상위 N개 또는 상위 P% 종목에만
매수 신호를 허용하는 횡단면 모멘텀 필터(`RankingFilter`)를 추가했습니다.
PR #97 머지 커밋 `2bd01b1`. 신규 테스트 13건, 전체 1179 통과, 린트 깨끗.

## 배경 — 세계 최고 수준 격차 분석 결과

이 세션에서 세계 최고 수준 격차를 분석했을 때 가장 큰 격차는
**횡단면 순위 선택**이었습니다.

| 레이어 | 기존 | 스펙 021 후 |
|--------|------|-------------|
| 종목 선택 | 종목별 고정 룰(정적) | 전체 유니버스 실시간 순위 → 상위 N 동적 선택 |
| 시계열 모멘텀 | ✅ (스펙 018) | ✅ |
| 횡단면 모멘텀 | ❌ | ✅ |
| ERC 사이징 | ✅ (스펙 019·020) | ✅ |
| 레짐 필터 | ✅ (스펙 020) | ✅ |

Jegadeesh & Titman(1993) 이래 가장 강건하게 검증된 팩터:
최근 수익률 상위 종목이 이후 1~12개월간 하위 종목을 유의미하게 초과 수익.

## 변경 사항

### `strategy/ranking.py` (신규, 비커널)
- `cross_sectional_momentum(symbol_bars, period)`: 유니버스 전체를 N-기간 수익률
  내림차순 정렬. 바 부족 심볼은 `-Inf` 센티넬로 맨 뒤.
- `is_top_n(symbol, ranked, n)`: 상위 n위 이내이면 True.
- `is_top_pct(symbol, ranked, pct)`: 상위 pct% 이내이면 True.

### `config/rules.py` (비커널)
- `RankingFilter` Pydantic 모델:
  - `universe: tuple[str, ...]` — 순위 매길 전체 심볼(최소 2개).
  - `period: int` — 모멘텀 룩백(바 단위).
  - `top_n: int | None` — 상위 N개 허용.
  - `top_pct: float | None` — 상위 pct% 허용.
  - `top_n`과 `top_pct` 중 정확히 하나만 설정(모델 검증).
  - `qualifies(symbol, ranked)` 내장 헬퍼.
- `TradingRule.ranking_filter: RankingFilter | None = None` 필드 추가.
  `None`이면 기존 경로 byte 동일(옵트인).

### `execution/order_router.py` (비커널)
- 레짐 배율 적용 이후, 판단 자문 이전에 랭킹 필터 블록 삽입.
- `rule.ranking_filter`가 있으면 유니버스 전체 심볼 바를 DB에서 조회 →
  `cross_sectional_momentum()` → `rf.qualifies()` → 미통과 시
  `OrderOutcome(state="SKIPPED_BY_RANKING", reason="not_in_top")` 반환.

### `backtest/replay.py` (비커널)
- 각 세션 날짜 루프에서 레짐 이후, 한도 계산 이전에 동일한 랭킹 필터 적용.
- `b.session_date <= session_date` 필터로 미래 바 참조 방지(lookahead 없음).

## 안전 경계

- **Kernel 터치 0건**: `risk/gates.py`(K1) 변경 없음.
- **하향 전용**: 필터는 주문을 스킵할 뿐 수량을 늘리지 않음.
- **옵트인**: `ranking_filter=None`이면 기존 경로 byte 동일.
- **결정론적**: 동일 바 데이터 → 동일 순위(Decimal 정렬). 백테스트=라이브 단일 잣대.
- **`AUTO_INVEST_MODE=live` 전환 미포함**: 여전히 운영자 명시 지시 필요.

## 테스트 (`tests/unit/test_spec_021_ranking.py`) — 13개

- 유닛: `test_cross_sectional_momentum_order`, `test_insufficient_bars_goes_last`,
  `test_is_top_n_pass`, `test_is_top_n_fail`, `test_is_top_pct_boundary`,
  `test_ranking_filter_requires_exactly_one_selector`, `test_ranking_filter_universe_min_size`
- SC-01: 3종목 유니버스 1위 → top_n=2 통과(PAPER_FILLED)
- SC-02: 3위 → top_n=2 미통과(SKIPPED_BY_RANKING)
- SC-03: top_pct=50, 4종목에서 3위 이하 스킵
- SC-04: 바 부족 심볼은 순위 맨 뒤 → 스킵
- SC-05: `ranking_filter=None` → 기존 경로 동일(옵트인 회귀 보호)
- SC-06: 백테스트 replay에서 하락 종목 주문 수 < 상승 종목 주문 수

전체 1179 통과, 4 스킵(라이브 KIS smoke), 린트 깨끗.

## 실거래 전환 가능성 평가 (이 세션 분석)

| 항목 | 상태 |
|------|------|
| 안전 게이트(K1 포지션 한도) | ✅ 완성 |
| 손실 서킷 브레이커(스펙 014) | ✅ 완성 |
| 체결 동기화(스펙 015) | ✅ 완성 |
| 일일 정합성(스펙 001 T050) | ✅ 완성 |
| 하드닝 캐너리(스펙 007) 실행·통과 | ⚠️ **미실행** — 배포 게이트 |
| 페이퍼 트레이딩 실적 | ⚠️ 이 컨테이너에서 접근 불가 |

**결론**: 아키텍처는 준비됐으나 헌법 VI조(Backtest→Canary→Full Live)에 따라
스펙 007 캐너리를 실제로 돌려 `CANARY_PASSED` 감사 이벤트를 기록해야
`AUTO_INVEST_MODE=live` 전환이 가능합니다. 5% 소자본 캐너리 시작 권장.

## 다음 후보

1. **퀄리티 팩터(스펙 022 후보)** — ROE·수익성·재무 건전성 기반 필터.
   한국 주식 시장에서 강건하게 검증된 팩터. 횡단면 필터 인프라 위에 바로 추가 가능.
2. **포트폴리오 최적화(스펙 023 후보)** — 평균분산(Markowitz) 또는 Black-Litterman으로
   샤프 비율 직접 최대화. ERC 대비 추가 알파.
3. **실거래 캐너리 전환** — 캐너리 실행 후 통과 시 `AUTO_INVEST_MODE=live` 토글.
   **운영자 명시 지시 필요**.
