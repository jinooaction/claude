# 스펙 030 — 체결 정교화 P2: 미체결 주문 수명 관리

## 배경 / 문제

스펙 028(체결 품질 정밀 측정)이 **arrival 기준 구현격차**와 **체결 지연**을 측정 가능하게
만들었다. 그 측정이 드러낸 두 가지 비효율이 이 스펙의 정당화 근거다:

1. **늙은 미체결 주문이 방치된다.** 지정가 주문이 시장에서 멀어지면 영원히 미체결로 남아
   `orders.state = SUBMITTED` 인 채 묶인다. 자본이 묶이고, 신호가 식은 뒤에도 체결될 위험이
   있다(스테일 체결). 현재는 미체결을 취소하는 자동 경로가 전혀 없다.
2. **지정가가 시장을 못 따라간다.** 가격이 벌어지면 지정가 주문은 체결되지 않고, 그렇다고
   다시 호가를 내는 로직도 없다. 측정된 체결 지연·구현격차의 상당 부분이 여기서 발생한다.
3. **시장가 주문은 슬리피지가 무제한이다.** `order_type=MARKET` 은 빠르게 체결되지만 얼마에
   체결될지 통제할 수 없다. 빠른 체결과 슬리피지 상한을 **동시에** 얻는 중간 수단이 없다.

## 목표

- **G1 — 미체결 TTL 취소**: 룰이 지정한 `ttl_seconds` 를 초과한 미체결 주문을 자동 취소한다.
- **G2 — 취소-재호가(cancel-replace)**: 지정가가 현재 중간가에서 `requote_drift_pct` 이상
  벌어진 미체결 지정가 주문을 취소하고, **게이트 체인을 다시 통과시켜** 신선한 가격으로 재제출한다.
- **G3 — marketable-limit**: 제출 시 시장가에 가까운 공격적 지정가(매수 = ask 약간 위, 매도 =
  bid 약간 아래)를 써서 빠른 체결과 슬리피지 상한(`marketable_limit_bps`)을 동시에 얻는다.

## 안전 경계 (비협상)

- **Kernel 터치 0건.** 커널(`worker/schedule.py`·`risk/gates.py`·`config/caps.py`)을 한 바이트도
  안 바꾼다. 재호가도 **K1 캡 게이트 체인을 다시 통과** — 노출 상한은 그대로 바인딩된다.
- **옵트인.** `TradingRule.lifecycle` 가 `None`(기본)이면 모든 경로가 byte 동일 — 기존 룰은
  주문 수명 관리를 전혀 받지 않는다(회귀 무손상).
- **취소는 브로커 확인 우선.** 브로커 `cancel_order` 가 성공한 **뒤에만** 로컬 상태를 CANCELLED 로
  전이한다. 취소 실패(이미 체결/종료)는 격리되어 상태를 안 바꾸고, 다음 체결 동기화(스펙 015)가
  실제 체결을 정합화한다. 부분 체결분은 `fills` 에 별도 기록돼 누락되지 않는다.
- **측정 단일 잣대(헌법 X.2).** marketable-limit 가격 계산은 결정론적 Decimal — 페이퍼/라이브
  동일 코드.
- **거래 무중단.** 수명 관리의 모든 예외는 격리되어 틱을 깨지 않는다. 호가 조회 실패 종목은
  재호가만 건너뛴다(TTL 취소는 호가 불필요).
- **dry-run/paper 그대로.** paper 모드는 `orders` row 가 없어 수명 관리가 호출되지 않는다.
- **재호가 폭주 방지.** 재호가는 `requote_after_seconds` 경과 후에만 고려되고, 재제출된 주문은
  새 `submitted_at` 을 받아 그 시간만큼 다시 재호가 대상에서 빠진다.

## 기능 요구사항

- **FR-030-01** — `OrderLifecycleConfig` (비커널, `config/rules.py`): `ttl_seconds: int | None`,
  `requote_drift_pct: Decimal | None`, `requote_after_seconds: int = 30`,
  `marketable_limit_bps: int | None`. `TradingRule.lifecycle: OrderLifecycleConfig | None = None`.
- **FR-030-02** — `marketable_limit_price(side, *, bid, ask, buffer_bps)` (순수, `execution/lifecycle.py`):
  매수 = `ask × (1 + bps/10000)` 올림(cent), 매도 = `bid × (1 − bps/10000)` 내림(cent). 호가
  없으면 `None`(호출자가 기존 표현식으로 폴백).
- **FR-030-03** — 제출 경로(`execution/order_router.py`): 지정가 주문이고 `rule.lifecycle.marketable_limit_bps`
  가 설정돼 있으면 limit_price 를 marketable 로 계산. 호가 없으면 기존 `limit_price` 표현식 폴백.
- **FR-030-04** — 미체결 로더(`execution/lifecycle.py`): 열린 주문(SUBMITTED/PARTIALLY_FILLED, kis_order_id
  있음)을 `correlation_id, kis_order_id, symbol, side, rule_id, order_type, limit_price_usd,
  submitted_at_utc, state` 로 읽는다.
- **FR-030-05** — 순수 계획(`plan_order_lifecycle`): 각 열린 주문에 대해 TTL 만료면 `cancel_ttl`,
  아니면(지정가 + 드리프트 임계 초과 + 최소 경과) `requote` 를 계획. 부수효과 없음(결정론 테스트).
- **FR-030-06** — 워커 배선(`worker/loop.py`): cadence(`_LIFECYCLE_GAP_SECONDS`)로 미체결 수명 관리.
  취소(브로커) → 상태 전이 CANCELLED → 감사. 재호가는 추가로 `router.submit_order` 로 재제출
  (게이트 체인 재통과). lifecycle 설정 있는 룰이 0건이면 아예 동작 안 함.
- **FR-030-07** — 감사(K4 추가-전용): `ORDER_TTL_CANCELLED`(kis_order_id, age_seconds, ttl_seconds,
  cancelled_at_utc), `ORDER_REQUOTED`(old_kis_order_id, old_limit_price_usd, mid_price_usd, drift_pct,
  requoted_at_utc). 기존 이벤트/row 무변경.

## 합격 지표

- **SC-030-01** — marketable BUY: ask=$100, bps=20 → limit=$100.20(올림). marketable SELL: bid=$100,
  bps=20 → limit=$99.80(내림). 호가 없음 → `None`.
- **SC-030-02** — TTL 만료: submitted 120초 전 + ttl=60 → `cancel_ttl`. submitted 30초 전 + ttl=60
  → 액션 없음.
- **SC-030-03** — 드리프트 재호가: limit=$100, mid=$103, drift_pct 임계=2%, 경과 60s ≥ 30s →
  `requote`(drift=3%). drift 1% < 2% → 액션 없음. 경과 10s < 30s → 액션 없음(시간 미달).
- **SC-030-04** — TTL 우선: 만료 + 드리프트 동시 → `cancel_ttl`(재호가보다 우선, 늙은 주문 정리).
- **SC-030-05** — 옵트인: `lifecycle=None` 룰의 열린 주문은 계획에서 제외(액션 0건).
- **SC-030-06** — 워커: TTL 만료 주문 → `cancel_order` 호출 + CANCELLED 전이 + `ORDER_TTL_CANCELLED`
  감사 1건. 재호가 → 취소 + `ORDER_REQUOTED` + `submit_order` 재호출(게이트 체인 재통과).
- **SC-030-07** — 취소 실패 격리: `cancel_order` 가 예외면 상태를 안 바꾸고 틱이 안 깨진다.
- **SC-030-08** — 시장가 주문은 재호가 대상 아님(limit_price 없음). marketable_limit_bps=None 이면
  제출 가격은 기존 표현식 그대로(byte 동일).

## 비목표

- KIS 실시간 웹소켓 시세/체결통보(폴링 지연 제거)는 **스펙 031(P3)**.
- 주문 분할(child order)·아이스버그·TWAP/VWAP 알고리즘은 이 스펙 범위 밖.
- 부분 체결 잔량의 정교한 재추적(누적 평균가 외)은 스펙 015 범위 유지.
