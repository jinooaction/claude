# 스펙 032 — 횡단면 포트폴리오 재조정 엔진 (Cross-Sectional Portfolio Rebalancing)

## 한 줄 요약

유니버스 전체를 합성 알파 점수로 매겨 **목표 포트폴리오**(상위 N개, 리스크 모델
가중)를 구성하고, 현재 보유와의 **차이를 매수+매도 주문으로 재조정**하는 엔진을
추가한다. 일정 주기로 반복하며, 회전율을 통제한다. 슬라이스 1은 **순수 플래너 +
백테스트 통합 + 수익률 측정**까지(라이브 배선은 후속 슬라이스, 운영자 게이트).

## 배경 — 세계 최고 수준 격차

기존 시스템은 **룰 중심**이다. 각 룰은 한 종목·한 방향(주로 매수)으로, 자기
트리거가 발화하면 고정 수량을 주문한다. 스펙 021/023/025의 횡단면 필터·스펙
017/019/020의 사이징·스펙 022/024의 포트폴리오 최적화기는 모두 **룰 한 개의 단일
종목 맥락 안에서 주문을 줄이거나 건너뛰는 보조 장치**로만 붙어 있다.

이 구조에는 세계 최고 수준 계량 주식의 핵심 두 가지가 **통째로 빠져 있다**:

1. **목표 포트폴리오라는 개념이 없다.** "지금 이 유니버스에서 상위 N개를 이런
   비중으로 들고 있어야 한다"를 계산하는 곳이 없다.
2. **재조정(매도)이 없다.** 종목이 순위에서 밀려나도 아무도 팔지 않는다. 오른
   종목을 덜어내지도, 비중이 틀어져도 맞추지도 않는다. 알파가 새어 나간다.

세계 최고 수준은 **포트폴리오 중심**이다: ① 유니버스 점수화 → ② 목표 비중 구성
(상위 N개, 리스크 모델 가중) → ③ 현재 보유와 차이(diff) 계산 → ④ 매수+매도로
재조정 → ⑤ 일정 주기 반복(회전율·비용 통제). 이 "재조정 엔진"을 추가하면 이미
만들어 둔 알파 도구(`strategy/factors.py`·`strategy/sizing.py`의 최적화기)가
비로소 **분산된 실현 알파**로 표현된다. 이것이 단일 종목 매수 트리거 대비 가장 큰
수익률 격차다.

## 접근

새 모듈 `strategy/rebalance.py`(비커널, 순수 결정론 Decimal)가 두 단계를 한다.

### 1단계 — 목표 비중 (`target_weights`)

입력: 합성 점수 순위(스펙 025 `composite_scores` 재사용)와 종목별 종가 시계열.

1. 상위 `top_n`개(또는 `top_pct`%) 종목을 선택한다(데이터 부족 종목은 스펙
   021/023/025 규약대로 센티넬로 제외).
2. 선택 종목에 가중치를 부여한다(`weight_scheme`):
   - `"equal"`: 균등(1/N).
   - `"score_proportional"`: 합성 점수에 비례(점수를 양수로 평행이동 후 정규화).
   - `"inverse_vol"`: 역변동성 리스크 패리티(`realized_volatility` 재사용).
   - `"min_variance"` / `"max_sharpe"` / `"erc"`: 스펙 022/024의 최적화기 재사용
     (`covariance_matrix` → `min_variance_weights`/`max_sharpe_weights`/`erc_weights`).
     데이터 부족·수렴 실패 시 역변동성 → 균등 순으로 fallback(기존 모듈과 동일 규약).
3. 비중 합 = 1.0(롱-온리, 음수 없음). 결정론적 Decimal(6자리), 동점은 심볼명 순.

### 2단계 — 재조정 주문 (`rebalance_plan`)

입력: 목표 비중, 현재 보유 수량, 종목별 현재가, 가용 자본, 옵션.

1. 목표 금액 = `비중 × 자본 × invested_fraction`(현금 버퍼 유지). 목표 수량 =
   `floor(목표 금액 / 가격)`.
2. 보유와 차이(diff): `delta = 목표수량 − 현재수량`. `delta > 0` → 매수,
   `delta < 0` → 매도. **목표에 없는데 보유 중인 종목 → 전량 매도(청산)** — 이것이
   기존 시스템에 빠진 매도 차원이다.
3. **회전율 통제**: `rebalance_threshold_pct`(무거래 밴드) 미만의 작은 비중 변화는
   건너뛴다(잦은 소액 거래로 비용을 까먹지 않도록). `min_notional_usd`로 자투리
   주문도 거른다.
4. 결정론적 `PlannedOrder(symbol, side, qty)` 리스트 반환(심볼명 정렬).

플래너는 **수량을 제안만** 한다. 모든 주문은 라이브와 동일한 K1 게이트 체인
(`risk/gates.py`: whitelist·halt·per-trade·per-symbol·global)을 통과하며, 캡을
넘는 매수는 게이트가 변형 없이 거부한다 — 사이징과 동일 규약("플래너 제안, K1
바인딩"). 매도는 노출을 줄이므로 안전 경계를 넓힐 수 없다.

### 3단계 — 백테스트 통합 (`backtest/portfolio_replay.py`)

`replay_portfolio(...)`: 과거 봉을 순회하며 `rebalance_every_n_sessions`마다(또는
지정 요일에) 위 두 단계를 돌려 주문을 만들고, 게이트 체인을 통과시켜 백테스트
브로커로 체결한다. 각 세션 **마감가로 시가평가 자산곡선**을 누적한다. 미래 참조
금지(각 재조정일 **이하** 봉만 사용). 산출 지표는 기존 단일 잣대
(`backtest/metrics.py`: 총수익률·최대낙폭·샤프·소르티노 + 회전율)를 그대로 쓴다.

CLI `auto-invest backtest-portfolio` 가 이 엔진을 돌려 **재조정 포트폴리오의
수익률 프로파일**을 출력한다(text/json).

## 기능 요구사항 (FR)

- **FR-R01**: `strategy/rebalance.py` 신규 — `PlannedOrder` 데이터클래스,
  `target_weights(...)`, `rebalance_plan(...)` 순수 함수. Decimal 결정론.
- **FR-R02**: `target_weights` 는 `weight_scheme` ∈ {equal, score_proportional,
  inverse_vol, min_variance, max_sharpe, erc} 를 지원하고, 데이터 부족·수렴 실패
  시 보수적 fallback(역변동성 → 균등). 비중 합 = 1.0, 롱-온리.
- **FR-R03**: `rebalance_plan` 은 목표에 없는 보유 종목을 **전량 매도**한다(청산
  차원). 무거래 밴드(`rebalance_threshold_pct`)·최소 명목(`min_notional_usd`)으로
  회전율을 통제한다.
- **FR-R04**: `config/rules.py` 에 `PortfolioRebalanceConfig` 모델 추가(universe,
  top_n/top_pct, weight_scheme, 합성 가중치·파라미터, invested_fraction,
  rebalance_every_n_sessions, lookback_bars, rebalance_threshold_pct,
  min_notional_usd). 검증: universe ≥ 2, top_n·top_pct 정확히 하나,
  invested_fraction ∈ (0,1], weight_scheme 화이트리스트.
- **FR-R05**: `backtest/portfolio_replay.py` 신규 — `replay_portfolio(...)` 가
  주기적 재조정을 돌려 자산곡선·주문·체결·회전율을 만든다. 모든 주문은 기존 게이트
  체인을 통과한다(라우터 동일). 미래 참조 없음(재조정일 이하 봉만).
- **FR-R06**: CLI `auto-invest backtest-portfolio`(text/json) — 재조정 백테스트의
  총수익률·최대낙폭·샤프·소르티노·회전율을 단일 잣대로 출력.
- **FR-R07**: 라이브 워커(`worker/loop.py`)·기존 룰 경로는 **무변경**(byte 동일).
  재조정 엔진은 백테스트·CLI 에서만 호출(라이브 배선은 후속 슬라이스).

## 합격 기준 (SC)

- **SC-01**: 점수 순위가 주어지면 `target_weights(top_n=N)` 는 정확히 상위 N개
  종목에만 양의 비중을 주고 합이 1.0 이다(equal 기준).
- **SC-02**: `weight_scheme="score_proportional"` 이면 점수 높은 종목이 더 큰
  비중을 받는다.
- **SC-03**: `weight_scheme="inverse_vol"` 이면 변동성 낮은 종목이 더 큰 비중을
  받는다(리스크 패리티).
- **SC-04**: 데이터 부족·최적화 수렴 실패 시 fallback(역변동성→균등)으로 항상
  유효한 합=1.0 비중을 낸다(예외 없이).
- **SC-05**: `rebalance_plan` 은 목표에 없는 보유 종목에 대해 전량 매도 주문을
  낸다(청산 차원 — 기존 시스템에 없던 동작).
- **SC-06**: 목표 비중 변화가 `rebalance_threshold_pct` 미만이면 주문을 내지
  않는다(회전율 통제). 임계 이상이면 차이만큼 매수/매도한다.
- **SC-07**: 모든 매수 주문은 K1 캡 게이트를 통과하며, 캡 초과분은 거부된다
  (게이트가 천장 — 플래너가 노출을 안전 경계 위로 올릴 수 없다).
- **SC-08**: 백테스트가 미래 참조를 하지 않는다(재조정일 이후 봉 미사용).
- **SC-09**: 결정론 — 같은 봉 입력이면 같은 주문·같은 자산곡선(라이브=백테스트
  단일 잣대 준비).
- **SC-10**: 재조정 백테스트의 자산곡선이 종목 하락으로 순위에서 밀린 보유를
  매도해 손실을 잘라내는 것을 정량 확인(매도 차원의 수익률 효과).
- **SC-11**: `PortfolioRebalanceConfig` 의 잘못된 입력(top_n·top_pct 동시/부재,
  빈 유니버스, invested_fraction 범위 밖, 알 수 없는 weight_scheme)은 검증 오류.
- **SC-12**: 라이브 워커·기존 백테스트 룰 경로 byte 동일(회귀 무손상).

## 안전 경계

- **Kernel 터치 0건**: `risk/gates.py`(K1)·`config/caps.py`·`config/whitelist.py`·
  `worker/schedule.py`·`persistence/audit.py` 무변경. 전부 `strategy/rebalance.py`
  신규 + `backtest/portfolio_replay.py` 신규 + `config/rules.py`·`cli.py` 비커널
  추가.
- **돈 무이동**: 백테스트·CLI 전용. 라이브 워커 룰 루프 무변경(byte 동일).
  라이브 배선·실제 재조정 주문은 **후속 슬라이스**이며 돈 움직이는 운용 변경이라
  **운영자 게이트**(헌법 VI·X.4, CLAUDE.md 자율 머지 중단 조건).
- **하향 전용 안전망 유지**: 플래너는 수량을 제안만, K1 캡 게이트가 천장. 매수는
  캡 초과 시 거부, 매도는 노출 축소라 안전.
- **롱-온리**: 음수 비중·공매도 없음(헌법 도메인 제약 — v1 공매도 금지).
- **결정론적 Decimal**: 백테스트 byte-equality + 라이브/백테스트 단일 잣대(헌법 X.2).
- **LLM 미사용**: 순수 수치(헌법 III 무관).
- **옵트인**: 기존 설정에 `portfolios` 없으면 모든 경로 byte 동일.

## 검증

새 알파/사이징 작업은 반드시 `auto-invest walk-forward`(스펙 016 슬라이스 3)로
표본 외 검증할 것 — 재조정 파라미터(top_n·weight_scheme·임계)가 한 기간에
과적합되지 않았는지 확인. 다중검정 보정은 `auto-invest deflated-sharpe`(스펙 027).

## 슬라이스 계획

- **슬라이스 1(이번)**: 순수 플래너(`strategy/rebalance.py`) + 설정 모델 +
  백테스트 통합(`backtest/portfolio_replay.py`) + CLI + 단위·통합 테스트. 라이브
  무배선, byte 동일.
- **슬라이스 2(후속, 운영자 게이트)**: 라이브 워커 배선 — 재조정 스케줄러를 워커
  루프에 옵트인 연결, 실제 매수+매도 주문을 게이트 체인으로 라우팅. 돈 경로 변경.
- **슬라이스 3(후속)**: 부분 체결·미체결 재호가(스펙 030 연계)·세금/비용 인지
  재조정·캐너리 룰셋 적용(운영자 승격 게이트).
