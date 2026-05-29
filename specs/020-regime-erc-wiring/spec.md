**상태**: 진행 중
**브랜치**: `claude/gifted-feynman-WQgNX`
**선행 스펙**: 019(레짐 인식·공분산 ERC 유틸리티)

## 배경

스펙 019로 레짐 감지기(`strategy/regime.py`)와 완전 공분산 ERC 사이징
(`strategy/sizing.py`)이 완성됐다. 그러나 두 유틸리티는 아직 거래 루프에
연결되지 않아 실제 주문 수량에 영향을 주지 않는다.

이번 스펙에서 `execution/order_router.py` 와 `backtest/replay.py` 두 경로에
레짐 배율과 ERC 그룹 가중치를 실제로 배선한다.

## 슬라이스 1: TradingRule 확장

### 기능 요구사항

- **FR-R01**: `TradingRule` 에 `regime_index_symbol: str | None = None` 필드 추가.
  값이 있으면 해당 심볼의 봉 데이터를 `RegimeDetector.detect()` 에 전달한다.
  없으면 레짐 적용 안 함 (기존 동작 byte 동일).
- **FR-R02**: `TradingRule` 에 `regime_scale: dict[str, Decimal] | None = None` 필드 추가.
  값이 있으면 기본 `DEFAULT_REGIME_SCALE` 을 오버라이드한다. 없으면 기본값 사용.

## 슬라이스 2: order_router 레짐·ERC 배선

### 기능 요구사항

- **FR-O01**: `OrderRouter` 의 `_group_scale()` 메서드(현재 이름 `_inverse_vol_group_scale`)
  를 확장해 `sizing.mode == "erc"` 일 때 `erc_group_scales()` 를 호출하고
  해당 룰의 ERC 가중치를 반환한다.
- **FR-O02**: `submit_order()` 에서 `rule.regime_index_symbol` 이 설정된 경우:
  1. `get_bars(conn, symbol=rule.regime_index_symbol, timeframe=sizing_timeframe)` 로 봉 조회
  2. `strategy.regime.detect(index_bars)` → `Regime`
  3. 규칙의 `regime_scale` 오버라이드(없으면 `DEFAULT_REGIME_SCALE`) 에서 배율 조회
  4. `apply_regime_scale(base_qty, scale)` 로 수량 조정
  5. 레짐 적용 결과를 `SizingDecisionPayload` 의 `regime` 필드(선택)로 감사 기록
  6. `apply_regime_scale` 결과가 0이면 `SKIPPED_BY_SIZING / regime_zero` 반환
- **FR-O03**: ERC 또는 레짐 처리는 기존 `_inverse_vol_group_scale` 과 동일 위치(사이징
  단계)에서 실행되며, K1 게이트 체인 **이전**에 완료된다.

## 슬라이스 3: replay 레짐·ERC 배선

### 기능 요구사항

- **FR-P01**: `replay._replay_group_scale()` 을 확장해 `sizing.mode == "erc"` 일 때
  `erc_group_scales()` 를 호출한다. 인터페이스는 현재 `inverse_vol` 경로와 동일.
- **FR-P02**: `replay` 루프 안에서 `rule.regime_index_symbol` 이 설정된 경우:
  1. 인덱스 심볼의 봉 중 현재 재생 날짜 이전 봉만 슬라이스해 사용 (미래 데이터 사용 금지)
  2. `detect(index_bars_up_to_now)` → `Regime`
  3. ERC/역변동성 그룹 스케일 계산 **이후** 레짐 배율 추가 적용
  4. 결과 qty 가 0이면 해당 바를 건너뜀 (orders 미생성)
- **FR-P03**: 기존 `inverse_vol` + `erc` 없는 룰 → 기존 동작 byte 동일.

## 성공 기준

- **SC-01**: `order_router` 에서 `regime_index_symbol` 설정 룰 → BEAR 레짐 시
  qty 가 base × 0.3 (내림) 으로 줄어든다.
- **SC-02**: `order_router` 에서 `mode="erc"` 룰 → `erc_group_scales()` 기반
  가중치가 `group_scale` 에 반영된다.
- **SC-03**: `replay` 에서 BEAR 구간 봉 → qty 감소 확인.
- **SC-04**: `replay` 에서 `mode="erc"` 룰 → ERC 가중치 적용.
- **SC-05**: `regime_index_symbol=None` 인 기존 룰 → 기존 수량 byte 동일.
- **SC-06**: `pytest` 전체 통과.
