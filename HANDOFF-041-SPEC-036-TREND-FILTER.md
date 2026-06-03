# HANDOFF 041 — 스펙 036: 절대 모멘텀 추세 필터 (드로다운 방어 오버레이, 2026-06-03)

main 머지 `8bee9c8`(PR #167). Kernel 터치 0건, 돈 0 이동, 기존 동작 보존(옵트인). 운영자
지시: "다시 이어서 진행해"(세계 최고 수준 + 실제로 돈 버는 것).

## 한 줄 요약

알파 스택에 **유일하게 빠져 있던 전략 범주** — 종목별 절대 모멘텀(시계열 추세) 게이트 —
를 추가했다. 자기 추세 위일 때만 보유하고, 아래로 내려가면 **현금으로 빠진다**(Faber GTAA /
Antonacci 듀얼 모멘텀). 드로다운 방어 오버레이. 옵트인, 끄면 기존 동작 byte 동일.

## 우선순위 판단 근거

- 스펙 035 로 "돈 버는지 판정하는 폐회로"가 생겼다 → 이제 **그 판정이 심판할 진짜 후보
  전략**을 넣을 차례다.
- 데이터가 반복해서 보여준 세 실패(`REAL-DATA-FINDINGS.md`): ① 회전율·비용이 수익 잠식,
  ② 목표 비중 되돌리기가 강세장에서 승자를 덜어냄, ③ 좁은 유니버스.
- 알파 스택(모멘텀·퀄리티·저변동성·최소분산·최대샤프·ERC)에 유일하게 빠진 범주 = **종목별
  절대 모멘텀 추세 게이트**. 기존 `strategy/regime.py` 는 *시장 전체* qty 배율이라 다르다.
- 이게 소매 시스템이 단순 보유 대비 *실제로 가치를 더하는* 지점이다 — 강세장 raw 수익이
  아니라 **드로다운 방어로 위험조정 수익(샤프·칼마)을 한 사이클에 걸쳐 올림.** 세 실패를 정면
  대응: 회전율↓(신호 드묾), 승자 안 덜어냄(보유/현금 이진), 드로다운 방어(폭락 전·중 현금).
- 검증 데이터가 컨테이너에 없으니, 이건 *후보*로 추가하고 판정은 forward 트랙 + 스펙 035 가
  한다(stale 데이터로 엣지 주장 금지 — 함정 회피).

## 무엇을 만들었나

- **순수 모듈** `src/auto_invest/strategy/trend.py`(외부 의존성 0, Decimal만):
  - `above_trend(closes, spec)` — `sma`(종가 > lookback SMA) / `absolute_momentum`(후행수익률>0).
    데이터 부족이면 None(fail-safe).
  - `apply_trend_filter(weights, closes_by_symbol, spec)` — 추세 아래 종목 가중치 0(현금).
    **재정규화 안 함**(합 1 미만 = 나머지 현금 방어). 데이터 부족은 `on_insufficient`("hold"/
    "cash"). 입력 키 순서 보존(결정론). 종목별 `TrendDecision` 진단 반환.
  - `TrendSpec`(method/lookback/on_insufficient) — config 와 분리(결합도 최소).
- **`target_weights(..., trend=TrendSpec|None)`**(`strategy/rebalance.py`) — 가중치 산출 마지막에
  필터 적용. `trend=None` 이면 byte 동일. 기존 분기 로직은 `_base_weights` 로 추출(회귀 안전).
- **`TrendFilterConfig`**(`config/rules.py`, `[portfolio.trend_filter]`) + `PortfolioRebalanceConfig.
  trend_filter`(옵트인, 기본 None). **config 는 strategy 미임포트**(역방향 결합 회피).
- **호출부 배선**: `execution/rebalancer.py`(`_trend_spec` 헬퍼) + `backtest/portfolio_replay.py`
  가 config 필터를 `TrendSpec` 으로 변환해 전달 → **백테스트·라이브 양쪽 자동 적용.**
- 예시 `specs/036-trend-filter/example-trend-portfolio.toml`.

## 안전 경계 (지킨 것)

- **Kernel 터치 0건.** `risk/gates.py`·캡·whitelist·워커·감사 무변경. 롱-온리(현금으로만 빠짐,
  공매도 0 — 안전 경계 위로 노출 못 올림).
- **돈 0 이동, 기존 동작 보존.** `trend_filter` 미설정이면 가중치 경로 byte 동일(회귀 테스트
  `test_target_weights_trend_none_is_byte_identical` + `test_trend_filter_off_is_unchanged_behaviour`).
- **라이브 캐너리 미적용.** `deploy/canary-portfolio.toml` 안 건드림 — forward/캐너리에 추세
  필터를 켜는 것은 전략 변경이라 **운영자 결정.**
- **엣지 주장 금지.** 옛 데이터 백테스트는 *메커니즘*만 검증(폭락에서 현금 이탈 → 낙폭 감소).
  "지금 통하는가"는 forward 페이퍼 트랙 + 스펙 035 `forward-verdict` 가 판정.

## 검증

- 전체 `uv run pytest`: **1475 통과, 4 스킵**(라이브 KIS 게이트). 신규 22건:
  - 단위 `tests/unit/test_trend_filter.py` 20건(추세 판정·필터·spec 검증·config 라운드트립·
    target_weights 통합·결정론).
  - 통합 `tests/integration/test_spec_036_trend_filter.py` 2건(합성 폭락 낙폭 방어·미설정 회귀).
- 린트 `uv run ruff check src tests`: **All checks passed!**.
- 메커니즘 시연(합성 120세션 상승 후 60세션 −55% 폭락, top_n=2 equal): 추세 필터(sma 40)
  **ON 의 최대낙폭 < OFF** = 폭락에서 현금 이탈이 실제로 작동.

## 다음 세션이 이어받을 것

- **추세 필터를 forward 트랙에 올려 판정받기**(권장 다음 단계, 운영자 결정 사항): forward
  페이퍼 트랙(또는 별도 후보 포트폴리오)에 `[portfolio.trend_filter]` 를 켜면, 스펙 035
  `forward-verdict` 가 추세 오버레이가 단순 보유를 위험조정으로 이기는지 자동 판정한다. 단,
  하나의 forward 트랙에 여러 후보를 동시에 올리려면 NAV/체결을 portfolio_id 로 분리해야 한다
  ("forward 전략 토너먼트" — 별도 슬라이스).
- **후속 결합 후보**: ① 시장 레짐(스펙 019)과 결합(약세 레짐일 때만 필터 강화), ② 추세 결정을
  감사 이벤트로 기록(포렌식), ③ 듀얼 모멘텀(절대+상대) 결합.
- **여전한 큰 그림**: 옛 데이터로는 어떤 전략도 단순 보유를 못 이겼다(정직). 진짜 답은 현재
  데이터 forward 트랙 누적 + 스펙 035 판정. 추세 필터는 그 트랙에 올릴 **가장 유망한 첫 후보**다.
