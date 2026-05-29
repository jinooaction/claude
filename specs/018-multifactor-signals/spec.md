**상태**: 슬라이스 1 진행 중
**브랜치**: `claude/intelligent-meitner-DtzD5`

## 배경

스펙 017로 리스크 사이징 토대(변동성 타깃팅·역변동성·상관 헤어컷)가 완성됐다.
세계 최고 수준 퀀트 시스템과의 다음 격차는 **신호/알파 레이어** — 현재 신호가
EMA 교차·RSI 임계값 두 가지뿐이다. 학문적으로 가장 강건한 팩터를 추가한다:

1. **모멘텀 (시계열)** — N기간 수익률이 임계값 위/아래. 추세 추종의 기반.
2. **볼린저 밴드 %B (평균회귀)** — 밴드 내 상대 위치. 과매수·과매도 포착.

두 신호 모두 비커널, 옵트인(기존 룰 미변경), 스펙 017 사이징 인프라 위에서 동작한다.

## 슬라이스 1: 모멘텀·평균회귀 신호

### 기능 요구사항

- **FR-S1-01**: `momentum(bars, period)` → Decimal %. `(close[-1]/close[-1-period] - 1) * 100`.
  period+1 막대 미만이면 `IndicatorError`.
- **FR-S1-02**: `bollinger_band_pct_b(bars, period, std_dev)` → Decimal.
  `(close - lower) / (upper - lower)`. 밴드 폭 0이면 `IndicatorError`.
  `std_dev` 기본 2.0.
- **FR-S1-03**: 트리거 `MOMENTUM_ABOVE` / `MOMENTUM_BELOW` — params: `period`(int), `threshold`(Decimal).
- **FR-S1-04**: 트리거 `BB_ABOVE` / `BB_BELOW` — params: `period`(int), `std_dev`(float, 기본 2.0), `threshold`(Decimal).
- **FR-S1-05**: 기존 EMA 교차·RSI 트리거는 byte 동일.

### 성공 기준

- **SC-S1-01**: momentum(period=1) — 당일 수익률 양수이면 MOMENTUM_ABOVE 0 → True.
- **SC-S1-02**: bollinger_band_pct_b — 종가가 상단 밴드이면 %B ≈ 1.0.
- **SC-S1-03**: 기존 테스트 전부 통과.

## 슬라이스 2: 사이징 결정 감사 기록

### 기능 요구사항

- **FR-S2-01**: `audit.py`에 `SIZING_DECISION` 이벤트 추가 (K4 추가-전용, 기존 이벤트 무변경).
- **FR-S2-02**: `SizingDecisionPayload`: rule_id, symbol, base_qty, final_qty,
  realized_vol_pct(Optional), vol_scale(Optional), group_scale, sizing_mode.
- **FR-S2-03**: `sizing.py`에 `SizingResult` 데이터클래스 + `sized_quantity_with_result()`.
- **FR-S2-04**: `order_router.py`에서 sizing 적용 후 `SIZING_DECISION` 감사 기록.
- **FR-S2-05**: `final_qty=0`(사이징으로 스킵)도 기록. 옵저버빌리티.

### 성공 기준

- **SC-S2-01**: order_router submit_order가 sizing 적용 시 SIZING_DECISION 행 1건 기록.
- **SC-S2-02**: fixed 모드는 SIZING_DECISION 미기록(노이즈 방지).
- **SC-S2-03**: 기존 테스트 전부 통과.
