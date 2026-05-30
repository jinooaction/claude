# HANDOFF 038 — 스펙 028: 체결 품질 정밀 측정 (arrival 기준 구현격차 + 체결 지연, 2026-05-30)

main 머지 커밋 **`1dd665e`** (PR #116). K4 터치 커밋 **`589187a`**(감사 로그, 추가-전용).
운영자 지시 "세계 최고 수준이 되려면 — 결국 매수/매도가 얼마나 **실시간**에 가깝고,
**정확**하고, **정교**하게 동작하는지가 중요하지 않냐"에 대한 **P1(측정)** 작업.

## 왜 1순위였나 (세계 최고 수준 격차)

세계 최고 데스크의 비협상 기준은 "**개선하려면 먼저 측정**"이다. 매매 시스템의 실시간·정확·
정교를 끌어올리려면, 먼저 "지금 우리 체결이 얼마나 벗어나고 얼마나 늦는가"를 숫자로 알아야
한다. 그런데 기존(스펙 011 성과 엔진)에는 다음 공백이 있었다.

- **라이브 슬리피지 기준가가 지정가(`ORDER_INTENT.limit_price_usd`)였다.**
  - 시장가(MARKET) 주문은 `limit_price=None` → 기준가 없음 → **"측정 불가"로 영원히 빠짐**.
  - 지정가 주문도 "전략이 정한 지정가" 대비라서, "내가 결정할 때 본 시장가(arrival price)"
    대비 **진짜 구현격차(implementation shortfall)** 가 아니었다.
- **모드별 잣대 불일치**: 페이퍼는 결정 시점 시세 기준, 라이브는 지정가 기준 → 같은 전략의
  페이퍼·라이브 체결 품질을 직접 비교 불가(스펙 016 "단일 잣대" 정신 위배).
- **체결 지연 미측정**: 의사결정(`ORDER_INTENT`)→체결(`FILL`)까지 몇 초 걸렸는지 집계가 없었다 —
  실시간성의 핵심 지표가 통째로 빠져 있었다.

## 무엇을 했나 (측정 전용 — 주문 경로 한 바이트도 안 바꿈)

- **`persistence/audit.py`(K4 터치, 추가-전용)**:
  - `OrderIntentPayload`에 선택 필드 `decision_price_usd`/`decision_bid_usd`/`decision_ask_usd`
    추가 — 결정 순간의 arrival 시세·호가. 기본 None이라 과거 row는 자연 폴백.
  - `LivePerformanceSnapshotPayload`에 선택 필드 `avg_fill_latency_sec`/`median_fill_latency_sec`/
    `measurable_latency_fills` 추가 — 자율 튜너(스펙 005)가 시계열로 소비.
  - **추가-전용 선택 필드만** 더했고 기존 이벤트·컬럼·row는 무수정 → 헌법 IV(append-only) 보존.
    안전 경계 변경 아님(K-meta 아님 → 커밋 메시지 "safety perimeter" 문자열 불필요).
- **`execution/order_router.py`(비커널)**: `ORDER_INTENT` 기록 시 결정 순간의
  `quote_price_usd`/`quote_bid_usd`/`quote_ask_usd`를 위 필드에 채운다. **그 외 주문 경로
  (게이트 K1·사이징·필터·판단·브로커 호출) 무변경.**
- **`performance/engine.py`(비커널)**:
  - `_read_live_fills`의 라이브 기준가 우선순위 = `decision_price_usd`(arrival, 있으면) →
    `limit_price_usd`(과거 row 폴백) → None. **시장가 주문도 측정 가능**해지고, 페이퍼(결정시
    last)·라이브가 같은 잣대(arrival)로 비교됨.
  - `FillRecord.decision_at_utc`(라이브는 `ORDER_INTENT.ts_utc`, 페이퍼는 None) 추가.
  - `compute_fill_latency`/`FillLatencyStats`/`render_latency_text`: 의사결정→체결 지연(초)을
    평균·중앙·p95·최대로 집계. 음수 지연(체결 ts < 결정 ts)은 경고로 분리.
  - `snapshot_fields(..., latency=...)` 선택 인자로 스냅샷에 지연 요약 평탄화.
- **`cli.py`(비커널)**: `auto-invest performance --slippage`가 체결 지연 섹션도 출력(text/JSON),
  `--snapshot`이 라이브일 때 지연 요약을 `LIVE_PERFORMANCE_SNAPSHOT`에 함께 기록.

## 안전 경계 (비협상)

- **측정만 한다.** 주문을 새로 내거나 취소·정정하지 않는다. 트레이딩 안전 불변량(헌법 I~VII·
  VIII.A)과 무관. 라이브 전환 토글(`AUTO_INVEST_MODE`) 무관.
- DB 마이그레이션 불필요(데이터는 schema-less `payload_json`에 실린다).
- 하위 호환: 과거 row(arrival 미기록)는 `decision_price_usd=None` → 라이브 기준가가 기존
  `limit_price_usd`로 자연 폴백.

## 검증

- 신규 테스트 +10: `tests/unit/test_performance_latency.py`(신규, 8건) + `test_performance_slippage.py`
  보강(arrival 우선·시장가 측정 가능) + `test_order_router.py` 보강(ORDER_INTENT arrival 기록).
- 합격 지표 SC-028-01~06 충족: 시장가 측정 가능 / arrival 우선·과거 row 폴백 / 4초 지연 /
  페이퍼 제외 / 기존 테스트 하위 호환 / 결정론(같은 audit_log → 같은 수치).
- 전체 **1260 통과, 4 스킵**(라이브 KIS smoke만), `ruff check src tests` 깨끗.

## 다음 세션 (체결 정교화 사다리 — 이 스펙은 P1)

- **P2 — 주문 수명 관리**: 미체결 지정가 TTL + 취소-재호가(cancel-replace) + marketable-limit.
  주문 경로(K-touch)를 바꾸므로 신중. **이 스펙(028)의 슬리피지 수치가 P2를 정당화하는 근거.**
  `cancel_order` 브로커 호출은 이미 있으나 워커 루프에 미배선.
- **P3 — KIS 실시간 웹소켓 시세/체결통보**: 1Hz REST 폴링(시세) + 5초 폴링(체결)을 푸시로
  대체해 지연 제거. 실시간성 최대 효과지만 연결 관리·검증 난이도 큼.
- 그 외 알파/리스크: 베타 인식 노출 조절, 합성 가중치 워크포워드, 풀라이브 승격 발화 로직
  (하드닝 캐너리 통과 시, 운영자 게이트).

스펙 문서: `specs/028-execution-quality-precision/spec.md`.
