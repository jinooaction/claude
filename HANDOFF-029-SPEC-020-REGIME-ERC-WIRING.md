# HANDOFF 029 — 스펙 020: 레짐 배율 + ERC 가중치 거래 루프 실배선 (2026-05-29)

## 한 줄 요약

스펙 019가 완성한 레짐 감지기(`strategy/regime.py`)·ERC 유틸리티(`strategy/sizing.py`)를
`execution/order_router.py`·`backtest/replay.py` 실제 거래 루프에 연결했습니다.
PR #95 머지 커밋 `cb5dcae`. 신규 테스트 5건, 전체 1166 통과, 린트 깨끗.

## 배경

스펙 019는 레짐 감지(SMA50/200 기반 TRENDING/RANGING/BEAR 3상태)와 완전 공분산 ERC
(Maillard CCD 반복 최적화, 등기여 위험 배분)를 완성했습니다. 그러나 두 함수는
유틸리티로만 존재했고 실제 주문 경로·백테스트 수량 계산에는 연결되지 않았습니다.
스펙 020이 그 배선 작업입니다.

## 변경 사항

### `config/rules.py` (비커널)
- `TradingRule`에 두 선택적 필드 추가:
  - `regime_index_symbol: str | None` — 레짐 판별에 쓸 인덱스 심볼(예: "SPY"). `None`이면 기존 동작 byte 동일.
  - `regime_scale: dict[str, Decimal] | None` — 레짐별 배율 오버라이드. `None`이면 `DEFAULT_REGIME_SCALE` 사용.
- `SizingConfig.mode`에 `"erc"` 추가(`"fixed"` / `"target_vol"` / `"inverse_vol"` / `"erc"`).

### `execution/order_router.py` (비커널)
- `_group_scale()` 신설: `inverse_vol`·`erc` 양 모드 지원. 기존 `_inverse_vol_group_scale()`은 이 함수의 alias로 유지(하위 호환).
  - `erc` 모드: DB에서 그룹 멤버 바 조회 → `erc_group_scales()` 호출 → 해당 rule_id 가중치 반환.
- 레짐 배율 적용 블록 추가(vol/ERC 사이징 **후**, 판단 자문 **전**):
  - `rule.regime_index_symbol`이 있으면 DB에서 인덱스 바 로드 → `detect_regime()` → 배율 결정 → `apply_regime_scale(qty, scale)`.
  - 결과 qty < 1이면 `OrderOutcome(state="SKIPPED_BY_SIZING", reason="regime_zero")` 반환.

### `backtest/replay.py` (비커널)
- `_replay_group_scale()` 확장: `erc` 모드 지원(세션 날짜까지의 바로 `erc_group_scales()` 호출).
- `symbols_in_use`: 레짐 인덱스 심볼을 포함해 필요한 모든 심볼 로드.
- 레짐 인덱스 심볼은 `date.min`부터 전 기간 바 로드(SMA-200 필요 때문에 날짜 범위 제한 없음).
- 각 세션 날짜 루프에서 레짐 판별 → `apply_regime_scale` → qty < 1이면 해당 세션 건너뜀.

### `strategy/sizing.py` (비커널)
- `sized_quantity()`: `mode="erc"`도 `inverse_vol`과 같은 `group_scale` 경로 사용. 호출자가 미리 계산한 ERC 가중치를 `group_scale`로 전달하면 동일 곱셈·내림 로직 적용.

## 안전 경계

- **Kernel 터치 0건**: `risk/gates.py`(K1) 변경 없음. 레짐·ERC는 K1 게이트 **전에** 수량을 줄이거나 건너뛰기만 — K1이 그대로 천장으로 작동.
- **하향 전용**: `DEFAULT_REGIME_SCALE` 최대 1.0(TRENDING), ERC 가중치 max 1 클램핑. 노출 증가 불가.
- **옵트인**: `regime_index_symbol=None`이면 기존 동작 byte 동일. 회귀 무손상.
- **결정론적**: 모든 계산이 `Decimal` 기반. 백테스트·라이브 단일 잣대(헌법 X.2).
- **감사 K4 무변경**: 기존 `SIZING_DECISION` 이벤트 그대로 사용.
- **dry-run 그대로**: `AUTO_INVEST_MODE=live` 전환은 운영자 명시 지시 필요.

## 테스트

`tests/unit/test_spec_020_wiring.py` — 5개 테스트:
- SC-01: 레짐 지수 없으면 수량 변화 없음(옵트인 회귀 보호)
- SC-02: TRENDING 레짐 → 배율 1.0 적용(수량 유지)
- SC-03: BEAR 레짐 → 배율 0.3 적용 + qty < 1이면 주문 건너뜀
- SC-04: 백테스트 replay에서 BEAR 구간 레짐 인식 → 주문 수 감소
- SC-05: ERC 모드 그룹 가중치 replay에서 적용

전체 1166 통과, 4 스킵(라이브 KIS smoke, `KIS_LIVE_TEST=1` 가드).

## 다음 후보

- ERC 모드 YAML 룰 예제 문서
- 교차 단면 모멘텀 랭킹(신호 과학 확장)
- 양방향 그룹 budget-split(K1 봉투 안 확대)
- 실거래 전환 `AUTO_INVEST_MODE=live` — **운영자 명시 지시 필요, 돈 움직이는 행동**
