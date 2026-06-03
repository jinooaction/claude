# 스펙 036 — 절대 모멘텀 추세 필터 (드로다운 방어 오버레이)

## 문제 (왜 이게 수익률의 다음 레버인가)

이 시스템의 정직한 측정은 반복해서 같은 결론을 냈다(`REAL-DATA-FINDINGS.md`): 가진 데이터로
시험한 **어떤 횡단면 재조정 설정도 비용 차감 후 단순 보유를 못 이긴다.** 세 가지 실패 모드가
일관됐다: ① 잦은 재조정의 회전율·수수료가 수익을 잠식, ② 목표 비중 되돌리기가 강세장에서
승자를 덜어냄, ③ 좁은 유니버스.

그런데 알파 스택(모멘텀·퀄리티·저변동성·최소분산·최대샤프·ERC)에 **유일하게 빠진 전략
범주**가 있다 — **종목별 절대 모멘텀(시계열 추세) 게이트**: 자기 추세 위에 있을 때만 보유하고,
아래로 내려가면 **현금으로 빠진다**(Faber GTAA, Antonacci 듀얼 모멘텀). 기존 `strategy/regime.py`
는 *시장 전체* qty 배율(0.3/0.7/1.0)이라 이것과 다르다 — 추세 필터는 *종목별* 보유/현금 이진
게이트다.

이게 중요한 이유: 소매 시스템이 단순 보유 대비 *실제로 가치를 더하는* 지점은 강세장 raw
수익이 아니라 **드로다운 방어로 위험조정 수익(샤프·칼마)을 한 사이클에 걸쳐 올리는 것**이다.
그리고 이 오버레이는 위 세 실패를 정면으로 푼다: 회전율 낮음(신호가 드묾), 승자 안 덜어냄
(보유/현금 이진), 드로다운 방어(폭락 전·중 현금 이탈).

## 목표

목표 가중치 산출 마지막에 적용되는 **옵트인·가산** 추세 게이트를 만든다 — 자기 추세 아래
종목은 가중치 0(현금)으로 빠지고, 합이 1 미만이 되며 그 차이는 현금 버퍼(방어)다. 끄면 기존
동작과 **byte 동일**. 백테스트·라이브 양쪽에 자동 적용(둘 다 `target_weights` 를 거치므로).

## 기능 요구 (FR)

- **FR-T01** `above_trend(closes, spec)` — 종가 시계열이 추세 위인지 결정론적 판정. `sma`(마지막
  종가 > lookback SMA) / `absolute_momentum`(lookback 후행수익률 > 0). 데이터 부족이면 None.
- **FR-T02** `apply_trend_filter(weights, closes_by_symbol, spec)` — 추세 아래 종목을 0(현금)으로.
  **재정규화 안 함**(나머지=현금). 데이터 부족은 `on_insufficient`("hold"/"cash") 정책으로.
  입력 키 순서 보존(결정론).
- **FR-T03** `target_weights(..., trend=TrendSpec|None)` — trend 주어지면 가중치 산출 후 필터 적용.
  None 이면 기존 동작 byte 동일.
- **FR-T04** `TrendFilterConfig`(`[portfolio.trend_filter]`, 옵트인) — method/lookback/
  on_insufficient. `PortfolioRebalanceConfig.trend_filter` 로 노출, 생략 시 None(미적용).
- **FR-T05** 백테스트(`portfolio_replay`)·라이브(`execution/rebalancer`) 호출부가 config 의 필터를
  `TrendSpec` 으로 변환해 `target_weights` 에 전달.

## 안전 경계 (비협상)

- **Kernel 터치 0건.** 신규 모듈 `strategy/trend.py` + config 모델 + `target_weights` 옵트인 인자.
  `risk/gates.py`·캡·whitelist·워커·감사 무변경. 롱-온리(현금으로만 빠짐, 공매도 0).
- **돈 0 이동, 기존 동작 보존.** `trend_filter` 미설정이면 가중치 경로 byte 동일(회귀 테스트로
  입증). 라이브 캐너리 룰셋(`canary-portfolio.toml`)은 **이 PR 에서 안 켠다** — 추세 필터를
  forward 트랙/캐너리에 켜는 것은 전략 변경이라 운영자 결정.
- **엣지 주장 금지.** 옛 데이터 백테스트는 *메커니즘*만 검증한다(폭락에서 현금 이탈 → 낙폭 감소).
  "지금 통하는가"의 판정은 forward 페이퍼 트랙 + 스펙 035 엣지 판정이 한다.

## 합격 기준 (SC)

- **SC-T01** 추세 위→유지, 아래→현금(0), 부족→정책대로(단위).
- **SC-T02** 필터는 재정규화 안 해 합이 1 미만이 될 수 있다(나머지=현금)(단위).
- **SC-T03** `trend=None` 이면 `target_weights` 결과가 기존과 동일(합 1.0)(단위·통합 회귀).
- **SC-T04** 합성 폭락 백테스트에서 필터 ON 의 최대낙폭 < OFF(메커니즘, 통합).
- **SC-T05** `[portfolio.trend_filter]` TOML 라운드트립 + 미설정 시 None + 알 수 없는 키 거부(단위).
- **SC-T06** 같은 입력 → 같은 결과(결정론). 전체 테스트·린트 통과.

## 다음

- 운영자가 forward 페이퍼 트랙(또는 별도 후보)에 추세 필터를 켜면(예시: `example-trend-portfolio.toml`),
  스펙 035 `forward-verdict` 가 추세 오버레이가 단순 보유를 위험조정으로 이기는지 자동 판정한다.
- 후속: 시장 레짐(스펙 019)과 결합(약세 레짐일 때만 필터 강화), 추세 결정 감사 이벤트 기록.
