# 스펙 028 — 체결 품질 정밀 측정 (의사결정가 기반 구현격차 + 체결 지연)

> 한 줄: **매수/매도가 "내가 결정한 순간 본 시장가"에서 얼마나 벗어나(정확) 얼마나 늦게(실시간)
> 체결됐는지**를 시장가 주문까지 포함해 한 잣대로 측정한다. 측정만 한다 — 주문을 더 내거나 취소하지 않는다.

## 배경 / 문제

세계 최고 수준의 매매는 결국 "체결이 얼마나 실시간에 가깝고, 정확하고, 정교한가"로 귀결된다.
그러나 **개선하려면 먼저 측정해야 한다.** 현재(스펙 011 성과 엔진)의 한계:

1. **라이브 슬리피지 기준가가 지정가(`ORDER_INTENT.limit_price_usd`)** 다.
   - 시장가(MARKET) 주문은 `limit_price=None` → 기준가 없음 → **"측정 불가"로 영원히 빠진다**.
   - 지정가 주문도 "전략이 정한 지정가" 대비라서, "결정 순간 시장가(arrival price)" 대비 **진짜 구현격차
     (implementation shortfall)** 가 아니다. 지정가는 통제 변수이지 시장 현실이 아니다.
2. **모드별 잣대 불일치**: 페이퍼는 결정 시점 시세(`reference_price_usd`) 기준, 라이브는 지정가 기준.
   같은 전략의 페이퍼·라이브 체결 품질을 직접 비교할 수 없다(스펙 016 "단일 잣대" 정신 위배).
3. **체결 지연 미측정**: 주문 의사결정(`ORDER_INTENT`)부터 실제 체결(`FILL`)까지 몇 초 걸렸는지
   집계하는 곳이 없다 — 실시간성의 핵심 지표가 통째로 빠져 있다.

## 목표 (정확 · 실시간)

- **G1 (정확)** 라이브 체결 품질의 기준가를 **의사결정가(arrival price = 결정 순간의 last 시세)** 로
  바꾼다 → 시장가 주문도 측정 가능해지고, 페이퍼/라이브가 같은 잣대(arrival 기준)로 비교된다.
- **G2 (실시간)** 의사결정→체결 **지연(초)** 을 집계한다(평균·중앙·p95·최대).
- **G3 (정교)** 결정 순간의 호가(bid/ask)도 기록해 향후 스프레드 인지 품질 분석의 토대를 만든다.

## 안전 경계 (비협상)

- **측정 전용.** 이 스펙은 주문을 새로 내거나 취소·정정하지 않는다. 게이트 체인(K1), 사이징,
  브로커 호출 경로는 **한 바이트도 바뀌지 않는다** — 헌법 I~VII·VIII.A 트레이딩 안전 불변량과 무관.
- **추가-전용(append-only).** `ORDER_INTENT`/`LIVE_PERFORMANCE_SNAPSHOT` 페이로드에 **선택 필드만 추가**
  한다(기본값 None). 기존 이벤트 타입·컬럼·row를 수정하지 않으므로 헌법 IV 위반 없음. DB 마이그레이션
  불필요(데이터는 schema-less `payload_json`에 실린다).
- **하위 호환.** 과거 row(arrival 미기록)는 `decision_price_usd=None` → 라이브 기준가가 기존
  `limit_price_usd`로 자연 폴백한다. 라이브 모드 전환 토글(`AUTO_INVEST_MODE`)과 무관.

## 기능 요구사항

- **FR-028-01** `OrderIntentPayload`에 선택 필드 추가: `decision_price_usd`, `decision_bid_usd`,
  `decision_ask_usd` (모두 `str | None = None`).
- **FR-028-02** `OrderRouter.submit_order`가 `ORDER_INTENT`를 기록할 때 위 필드를 결정 순간의
  시세(`quote_price_usd`/`quote_bid_usd`/`quote_ask_usd`)로 채운다. 그 외 라우터 동작 불변.
- **FR-028-03** `performance/engine._read_live_fills`의 라이브 기준가 우선순위:
  `decision_price_usd`(있으면) → `limit_price_usd`(과거 row 폴백) → None. 시장가 주문은 이제
  `decision_price_usd`로 측정 가능.
- **FR-028-04** `FillRecord`에 `decision_at_utc: str | None = None` 추가. 라이브는 같은
  correlation_id의 `ORDER_INTENT.ts_utc`. 페이퍼는 동기 체결이라 None(지연 측정 비대상).
- **FR-028-05** `compute_fill_latency(fills)` → `FillLatencyStats`: 측정 가능 건수, 평균/중앙/p95/최대
  지연(초). `decision_at_utc`가 있고 체결 ts ≥ 결정 ts인 체결만 측정. 음수 지연은 경고로 분리.
- **FR-028-06** `render_latency_text` + CLI `performance --slippage` 출력에 체결 지연 섹션 추가.
- **FR-028-07** `LivePerformanceSnapshotPayload`에 선택 필드 추가(`avg_fill_latency_sec`,
  `median_fill_latency_sec`, `measurable_latency_fills`)로 자율 튜너(스펙 005)가 시계열로 소비 가능.

## 합격 지표

- **SC-028-01** 시장가 라이브 주문 1건 + `decision_price_usd` 기록 → `compute_slippage`가 그 체결을
  **측정 가능**으로 집계한다(기존엔 측정 불가였음).
- **SC-028-02** `decision_price_usd`와 `limit_price_usd`가 둘 다 있으면 라이브 기준가는
  **`decision_price_usd`** 를 쓴다(arrival 우선). 둘 다 없는 과거 row는 `limit_price_usd` 폴백.
- **SC-028-03** 결정 13:00:00, 체결 13:00:04 인 라이브 체결의 지연 = **4.0초**로 집계된다.
- **SC-028-04** 페이퍼 체결은 지연 측정 대상에서 제외된다(`decision_at_utc=None`).
- **SC-028-05** 기존 슬리피지·성과 테스트가 전부 그대로 통과한다(하위 호환). `uv run pytest` 그린,
  `ruff check` 클린.
- **SC-028-06** 결정론: 같은 audit_log → 같은 체결 품질 수치(외부 API·시계 비의존, 주입 시각만 사용).

## 비목표 (후속 스펙)

- 주문 수명 관리(미체결 TTL, 취소-재호가, marketable-limit) — **P2**.
- KIS 실시간 웹소켓 시세/체결통보로 폴링 지연 제거 — **P3**.
- 실 OHLC 바 히스토리(합성 1-틱 바 대체) — 별도 축.
