# 스펙 021 — 횡단면 모멘텀 순위 필터

**상태**: 구현 완료  
**브랜치**: `claude/ecstatic-brahmagupta-iO11H`

## 배경

스펙 018로 시계열 모멘텀(단일 종목의 N기간 수익률)이 완성됐다. 그러나 세계 최고 수준
퀀트 시스템과의 가장 큰 격차는 **횡단면(크로스섹셔널) 순위** — 전체 유니버스 종목을
한꺼번에 순위 매겨 **상위 N개 또는 상위 P% 에만 매수 신호를 허용**하는 방식이다.

Jegadeesh & Titman(1993) 이래 가장 강건하게 검증된 팩터: 최근 수익률 상위 종목은
이후 1~12개월간 하위 종목을 유의미하게 초과 수익한다. 동일한 EMA/RSI 트리거를
모든 종목에 기계적으로 적용하는 방식 대비, 횡단면 필터는 "지금 이 유니버스에서
가장 강한 종목"만 선택해 알파를 집중시킨다.

## 기능 요구사항

- **FR-01**: `strategy/ranking.py` — `cross_sectional_momentum(symbol_bars, period)` 함수.
  입력: `dict[str, list[PriceBar]]`, 각 심볼의 바 리스트. 출력: `list[tuple[str, Decimal]]`
  — 모멘텀 내림차순으로 정렬된 (심볼, 수익률%) 리스트.
  바가 `period+1`개 미만인 심볼은 결과 리스트에 포함하되 맨 뒤로 밀림(`float('-inf')` 정렬 키).
- **FR-02**: `is_top_n(symbol, ranked, n)` → `bool`. 심볼이 ranked 리스트에서 상위 n위 이내이면 True.
  n > len(ranked) 이면 항상 True.
- **FR-03**: `is_top_pct(symbol, ranked, pct)` → `bool`. 상위 `pct`%(0 < pct ≤ 100) 이내이면 True.
  `top_n = max(1, ceil(len(ranked) * pct / 100))` 로 환산.
- **FR-04**: `config/rules.py` — `RankingFilter` Pydantic 모델 추가:
  - `universe: list[str]` — 순위를 매길 전체 심볼 목록(현재 심볼 포함).
  - `period: int` — 모멘텀 룩백 기간(바 단위).
  - `top_n: int | None = None` — 상위 N 개 허용.
  - `top_pct: float | None = None` — 상위 pct % 허용.
  - `top_n`과 `top_pct` 중 정확히 하나만 설정 가능(validator).
- **FR-05**: `TradingRule`에 `ranking_filter: RankingFilter | None = None` 필드 추가.
- **FR-06**: `execution/order_router.py` — `submit_order` 안에서, 레짐 배율 적용 후
  `rule.ranking_filter` 가 있으면 유니버스 모든 심볼 바를 DB 에서 조회해 순위 계산 →
  현재 심볼이 필터 통과 못하면 `OrderOutcome(state="SKIPPED_BY_RANKING", reason="not_in_top")`
  반환. 옵트인: `ranking_filter=None` 이면 기존 동작 byte 동일.
- **FR-07**: `backtest/replay.py` — 각 세션 날짜 루프에서 레짐 이후, 판단 이전에
  동일한 랭킹 필터 적용. 세션 날짜까지의 바만 사용(미래 데이터 참조 방지).
- **FR-08**: Kernel 터치 0건. `risk/gates.py`(K1) 변경 없음. 랭킹 필터는 K1 게이트
  **전에** 수량을 스킵할 뿐 — K1 이 그대로 천장으로 작동.

## 성공 기준

- **SC-01**: 유니버스 3종목 중 현재 심볼이 1위 → `top_n=2` 필터 통과.
- **SC-02**: 유니버스 3종목 중 현재 심볼이 3위 → `top_n=2` 필터 미통과 → `SKIPPED_BY_RANKING`.
- **SC-03**: `top_pct=50` — 4종목 유니버스에서 상위 2개(=50%) 허용, 3위 이하 스킵.
- **SC-04**: 바 부족 심볼은 순위 맨 뒤로 → 충분한 데이터 가진 심볼에 밀려 스킵.
- **SC-05**: `ranking_filter=None` 이면 주문 경로 byte 동일(옵트인 회귀 보호).
- **SC-06**: 백테스트 replay 에서 랭킹 필터 적용 시 하위 종목 주문 수 감소.
- **SC-07**: 기존 테스트 1166개 전부 통과.

## 안전 경계

- Kernel 터치 0건.
- 하향 전용: 랭킹 필터는 주문을 스킵할 뿐 수량을 늘리지 않는다.
- 옵트인: 기존 룰은 `ranking_filter` 없으므로 회귀 없음.
- 결정론적: 동일 바 데이터 → 동일 순위(Decimal 정렬).
- `AUTO_INVEST_MODE=live` 전환은 운영자 명시 지시 필요.
