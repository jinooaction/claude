# HANDOFF 028 — 상관 헤어컷 (스펙 017 슬라이스 3, 2026-05-29)

PR #89 머지 커밋 `33d3926`. **"세계 최고 수준" 로드맵 — 리스크 사이징 토대(변동성·역변동성·
상관)를 한 바퀴 완성**했습니다. 슬라이스 2b의 역변동성은 종목 간 상관을 0으로 가정했는데,
상관 높은 종목을 함께 들면 위험이 분산되지 않고 **집중**됩니다. 슬라이스 3은 그룹 멤버 간
수익률 상관을 재서, 상관 높은(분산 안 된) 멤버를 추가로 줄이는 **상관 헤어컷**을 더합니다.

## 왜 (이번 우선순위)

운영자가 "이어가"라고 지시했고, 직전 슬라이스 2b(HANDOFF-027)가 다음 후보로 "슬라이스 3
상관 인식 배분"을 지목했습니다. 슬라이스 2b의 `sizing_group` 인프라를 그대로 재사용합니다.

## 설계 결정 (애매성 해소)

상관 인식 사이징은 여러 형태가 가능합니다(완전 공분산 ERC 반복 최적화 / 상관 하드 합산
캡 / 상관 헤어컷). 가장 **보수적이고 추정 잡음에 강한** 형태를 골랐습니다:

- **상관 헤어컷 = 방어적 하향 통제.** 멤버 m의 헤어컷 = `1 - strength × max(0, 평균상관ₘ)`,
  `[0,1]` 클램프. 평균상관ₘ은 m의 최근 수익률과 그룹 내 다른 멤버 수익률의 평균 Pearson
  상관. 상관 ≤ 0(분산/역상관)이면 헤어컷 없음(1). 수익을 최적화하는 게 아니라 집중 위험을
  줄이는 거라, 상관 추정이 노이즈여도 "살짝 더 보수적"일 뿐 위험을 키우지 않는다(저-취약).
- **하향 전용.** 최종 그룹 가중치 = 역변동성 가중치(슬라이스 2b) × 상관 헤어컷. 둘 다 ≤ 1
  이라 곱도 ≤ 1 → 기준 수량 위로 노출을 못 올린다. K1이 그대로 천장.
- **완전 공분산 ERC·상관 하드 합산 캡은 후속**으로 미룸(범위 절제).

## 한 줄 요약

- **`config/rules.py`(비커널)**: `SizingConfig`에 선택적 `correlation_haircut`(강도, 기본
  `Decimal("0")`, `ge=0`, `le=1`). inverse_vol 그룹에서만 의미. 0이면 슬라이스 2b byte 동일.
- **`strategy/sizing.py`(비커널)**:
  - `pearson_correlation(xs, ys)` → 두 수익률 시계열의 Pearson 상관(분산 0/길이 불일치 None).
  - `average_correlations(closes_by_rule, lookback_bars)` → 멤버별 평균 상관. 멤버를 **공통
    거래일(날짜 교집합)**로 정렬해 최근 `lookback+1` 공통 종가로 수익률을 만든다. 공통일
    < 3이면 None(fail-safe).
  - `correlation_haircut(avg, strength)` → `1 - strength·max(0,avg)`, `[0,1]` 클램프.
  - `group_scale_for(rule_id, member_vols, closes_by_rule, lookback_bars,
    correlation_strength)` → 역변동성 가중치 × 상관 헤어컷을 한 번에 합성(양쪽 경로 공통).
- **백테스트·라이브 양쪽 연결(`backtest/replay.py`·`execution/order_router.py`, 비커널)**:
  둘 다 `group_scale_for`를 호출. 상관 입력은 멤버별 `{날짜: 종가}` 맵으로 넘기는데,
  백테스트는 `OHLCVBar.session_date`, 라이브는 `date.fromisoformat(PriceBar.bar_open_utc[:10])`
  로 같은 달력 날짜 키를 만든다 → 같은 교집합·같은 상관(헌법 X.2 단일 잣대).
  - `worker/loop.py`는 **이번엔 미변경** — 슬라이스 2b에서 이미 `build_sizing_groups`로
    그룹을 만들어 `OrderRouter.sizing_groups`로 넘기고 있어, 상관 필드는 기존 배선으로 흐른다.

## 안전 경계

- **하향 전용(헤어컷 ≤ 1, 역변동성 × 헤어컷도 ≤ 1) — 노출 증가 불가.** K1 캡이 사이징
  이후 변형 없이 실행돼 그대로 천장.
- **역상관/분산된 멤버는 헤어컷 없음**(`max(0, avg)`). 상관 < 0이면 1.
- **옵트인.** `correlation_haircut=0`(기본)이면 슬라이스 2b와 byte 동일(회귀 무손상).
  SC-S12 `test_replay_correlation_haircut_shrinks_correlated_basket`의 plain 경로로 증명.
- **Kernel 터치 0건.** 전부 `strategy/sizing.py`·`config/rules.py`·`backtest/replay.py`·
  `execution/order_router.py`(비커널)·`tests/`·`specs/`. 감사 스키마 K4 무변경.
- **결정론적·LLM 미사용.** dry-run 그대로(`AUTO_INVEST_MODE=live` 무관).

## 검증

- 테스트 신규 7건(전체 1110 통과, 4 스킵), 린트 깨끗.
- 핵심 증명:
  - SC-S12 `test_replay_correlation_haircut_shrinks_correlated_basket` — 상관 +1(같은 위상)
    바구니는 헤어컷으로 축소, `correlation_haircut=0`이면 풀 사이즈(슬라이스 2b byte 동일).
  - `test_replay_correlation_haircut_skips_anticorrelated` — 역상관(반대 위상)은 헤어컷 없음.
  - 순수 단위: `pearson_correlation`(±1·분산0·길이불일치), `average_correlations`(동위상 +1·
    역위상 -1·희소 fail-safe), `correlation_haircut`(케이스), `group_scale_for`(합성·강도 0).

## 다음 세션이 이어받을 것 (세계 최고 수준 로드맵)

리스크 사이징 토대(변동성 타깃팅 → 역변동성 그룹 패리티 → 상관 헤어컷)가 한 바퀴
완성됐습니다. 이제 규율 있는 순서상 **신호/알파 과학**을 리스크 사이징 위에서 진행할 수
있습니다:

- **신호/알파 과학** — 다요인(모멘텀·평균회귀·변동성)·레짐 인식·교차 단면 랭킹. 현재 신호는
  SMA·EMA·RSI + EMA 교차뿐(`strategy/indicators.py`·`triggers.py`). 새 신호는 각 신호를
  리스크 기여도로 사이징하고(스펙 017 인프라) 반드시 워크포워드로 표본 외 검증할 것.
- **스펙 017 후속**: 완전 공분산 ERC(등기여 반복 최적화)·상관 기반 하드 합산 캡·양방향
  그룹 budget-split(K1 봉투 안 확대)·사이징 결정 감사 기록(K4 추가-전용 — 실현 변동성·
  역변동성 가중치·상관·최종 수량을 포렌식 페이로드로).

**중요**: 새 사이징/알파 작업은 반드시 `auto-invest walk-forward`로 표본 외 검증할 것.
WFE가 낮거나 표본 외 우위가 사라지면 그 변경은 과적합이므로 채택하지 말 것.
