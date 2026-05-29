# HANDOFF 027 — 역변동성 그룹 리스크 패리티 (스펙 017 슬라이스 2b, 2026-05-29)

PR #87 머지 커밋 `b8fb7e9`. **"세계 최고 수준" 로드맵 — 멀티 포지션 리스크 배분 1단계**를
완성했습니다. 슬라이스 1·2가 **한 포지션**의 변동성만 봤다면, 슬라이스 2b는 **여러 종목을
한 바구니(sizing group)로 묶어** 종목 간 리스크 기여도를 균형화합니다.

## 왜 (이번 우선순위)

운영자가 "다음 우선순위 이어가"라고 지시했고, 직전 슬라이스 2(HANDOFF-026)가 다음 후보로
"슬라이스 2b 멀티 포지션 역변동성/리스크 패리티"를 지목했습니다. 이는 사이징 토대를 신호
과학보다 먼저 완성하는 규율 있는 순서(나중에 신호를 추가할 때 각 신호를 리스크 기여도로
사이징)를 잇고, 구조적 우위라 과적합 위험이 낮습니다(헌법 원칙 X).

## 설계 결정 (애매성 해소)

스펙은 슬라이스 2b를 한 줄("멀티 포지션 역변동성/리스크 패리티")로만 적었습니다. 가능한
해석 중 **현재 아키텍처에 단일 잣대(헌법 X.2)로 안전하게 맞는** 보수적 해석을 골랐습니다:

- **역변동성 = 상관 없는 리스크 패리티.** 그룹 멤버 가중치 = `min(그룹 멤버 실현변동성) /
  자기 실현변동성`, `(0, 1]`로 클램프. 변동성 가장 낮은 멤버가 기준(가중치 1, 풀 사이즈),
  높은 변동성 멤버는 그만큼 줄어 종목 간 per-share 위험이 맞춰진다.
- **하향 전용.** 가중치 ≤ 1이라 기준 수량 위로 노출을 올리지 않는다(슬라이스 1 불변량
  유지). 양방향 budget-split(그룹 총 예산을 K1 봉투 안에서 일부 확대)은 후속으로 미룸.
- **정적 룰셋 기반(동시 신호 상태 불필요).** 가중치는 (정적 룰셋 + 각 멤버 최근 바)에서만
  계산되므로, 룰을 하나씩 처리하는 라이브 라우터와 전체 룰을 보는 백테스트 양쪽에서 같은
  방식으로 계산할 수 있다 → 단일 잣대.

## 한 줄 요약

- **`config/rules.py`(비커널)**: `SizingConfig.mode`에 `"inverse_vol"` 추가. `TradingRule`에
  선택적 `sizing_group: str | None`(기본 None) 추가. `inverse_vol` 모드는 `sizing_group`
  필수(`@model_validator`로 강제). 둘 다 없으면 기존 동작 byte 동일.
- **`strategy/sizing.py`(비커널)**:
  - `SizingGroupMember`(rule_id·symbol·timeframe·lookback_bars) — 양쪽이 같은 방식으로
    변동성을 재게 하는 최소 메타.
  - `build_sizing_groups(rules)` → 그룹명 → enabled inverse_vol 멤버 목록.
  - `inverse_vol_group_scale(own_vol, member_vols)` → `min(measurable)/own`을 `(0,1]`로
    클램프. own 측정 불가(None/≤0)거나 측정 가능한 멤버가 없으면 1(fail-safe).
  - `sized_quantity`에 선택적 `group_scale`(기본 1) 추가 — `mode="inverse_vol"`이면
    `floor(기준수량 × group_scale)` 반환.
- **백테스트·라이브 양쪽 연결(`backtest/replay.py`·`execution/order_router.py`·
  `worker/loop.py`, 전부 비커널)**: K1 게이트 **전에** 같은 두 함수로 그룹 가중치를 계산해
  `sized_quantity`에 전달.
  - replay: 전체 룰·전 종목 바를 이미 보유 → `_replay_group_scale`이 멤버 변동성을 잰다.
  - 라이브: worker가 `build_sizing_groups(settings.config.rules)`로 그룹을 만들어
    `OrderRouter.sizing_groups`로 넘김. 라우터의 `_inverse_vol_group_scale`이 `self.conn`으로
    각 멤버 바를 `get_bars`로 조회해 같은 `realized_volatility`·lookback으로 잰다.

## 안전 경계

- **하향 전용(가중치 ≤ 1) — 노출 증가 불가.** K1 캡(`risk/gates.py`·`config/caps.py`)이
  사이징 이후 변형 없이 실행돼 그대로 천장으로 바인딩.
- **그룹은 옵트인.** `sizing_group` 없으면 기존 fixed/None/target_vol 룰과 byte 동일
  (회귀 무손상). SC-S11 `test_replay_no_group_is_byte_equal`로 증명.
- **Kernel 터치 0건.** 손댄 파일 전부 `strategy/sizing.py`·`config/rules.py`·
  `backtest/replay.py`·`execution/order_router.py`·`worker/loop.py`(비커널)·`tests/`·
  `specs/`. **주의: 커널은 `worker/schedule.py`이고 이번에 손댄 건 `worker/loop.py`(비커널)**.
  감사 스키마 K4 무변경(새 이벤트 0건).
- **결정론적·LLM 미사용.** 라이브·백테스트 단일 잣대(헌법 X.2). dry-run 그대로
  (`AUTO_INVEST_MODE=live` 무관).

## 검증

- 테스트 신규 8건(전체 1103 통과, 4 스킵), 린트 깨끗.
- 핵심 증명:
  - SC-S10 `test_replay_inverse_vol_group_shrinks_higher_vol_member` — 같은 그룹에서
    변동성 높은 AAPL(±2% 스윙)이 변동성 낮은 MSFT(±0.3%) 대비 줄고, MSFT는 풀 사이즈 유지.
  - SC-S11 `test_replay_no_group_is_byte_equal` — 그룹 없으면 기준 수량 그대로.
  - 순수 단위: `inverse_vol_group_scale`(최저=1·높은=축소·클램프·fail-safe),
    `build_sizing_groups`(enabled inverse_vol만), `sized_quantity` inverse_vol 모드,
    inverse_vol 모드의 `sizing_group` 필수 검증.

## 다음 세션이 이어받을 것 (세계 최고 수준 로드맵)

- **슬라이스 3** — 상관 인식 배분(상관 높은 종목 합산 리스크 한도). 공분산/상관 추정이
  필요하므로 역변동성보다 한 단계 복잡. 그룹 인프라(`sizing_group`)를 재사용할 수 있다.
- **양방향 그룹 budget-split** — 그룹에 총 리스크 예산을 줘 일부를 K1 봉투 안에서 확대
  (슬라이스 2b는 보수적 하향 전용만 했음). K1이 유일한 하드 상한이 되므로 게이트 통과
  재확인 필요(슬라이스 2와 같은 주의).
- **신호/알파 과학** — 다요인(모멘텀·평균회귀·변동성)·레짐 인식·교차 단면 랭킹. 현재
  신호는 SMA·EMA·RSI + EMA 교차뿐.
- **후속 K4(선택)** — 사이징 결정(실현 변동성·그룹 가중치·최종 수량)을 감사 페이로드로
  기록해 포렌식 가시성 확보(K4 추가-전용).

**중요**: 새 사이징/알파 작업은 반드시 `auto-invest walk-forward`로 표본 외 검증할 것.
WFE가 낮거나 표본 외 우위가 사라지면 그 변경은 과적합이므로 채택하지 말 것.
