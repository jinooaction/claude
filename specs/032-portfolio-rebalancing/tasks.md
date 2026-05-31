# 스펙 032 작업 — 횡단면 포트폴리오 재조정 엔진 (슬라이스 1)

## 슬라이스 1 (이번 세션 — 라이브 무배선, byte 동일) — 전부 완료 ✅

- [x] **T001** `config/rules.py` — `PortfolioRebalanceConfig` pydantic 모델 추가
  (universe, top_n/top_pct, weight_scheme, 합성 가중치·파라미터,
  invested_fraction, rebalance_every_n_sessions, lookback_bars,
  rebalance_threshold_pct, min_notional_usd) + 검증자. (FR-R04, SC-11)
- [x] **T002** `strategy/rebalance.py` 신규 — `PlannedOrder` + `target_weights(...)`
  (equal/score_proportional/inverse_vol/min_variance/max_sharpe/erc + fallback).
  (FR-R01, FR-R02, SC-01~04)
- [x] **T003** `strategy/rebalance.py` — `rebalance_plan(...)` (diff·전량매도청산·
  무거래밴드·최소명목). (FR-R03, SC-05, SC-06)
- [x] **T004** `tests/unit/test_spec_032_rebalance.py` — 단위 29건 통과. (SC-01~06, SC-09, SC-11)
- [x] **T005** `backtest/portfolio_replay.py` 신규 — `replay_portfolio(...)`
  (주기적 재조정 + 게이트 체인 + 자산곡선 + 회전율, 미래참조 방지). (FR-R05, SC-07~10)
- [x] **T006** `tests/integration/test_spec_032_portfolio_replay.py` — 통합 4건 통과
  (매도 청산·게이트 거부·자산곡선·결정론). (SC-05, SC-07~10)
- [x] **T007** `cli.py` — `backtest-portfolio` 명령(text/json, 단일 잣대 지표+회전율)
  + `example-portfolio.toml` 예시. (FR-R06)
- [x] **T008** 회귀 확인 — 기존 1348건 그대로 통과(총 1381건, 신규 33건), 린트 깨끗.
  라이브 워커·기존 백테스트 경로 무변경. (FR-R07, SC-12)

## 후속 슬라이스 (운영자 게이트 — 이번 세션 범위 밖)

- [ ] **T020** (슬라이스 2) 라이브 워커 배선 — 재조정 스케줄러 옵트인 연결, 실제
  매수+매도 라우팅. **돈 경로 변경 → 운영자 확인 필수.**
- [ ] **T021** (슬라이스 3) 부분 체결·재호가(스펙 030 연계)·캐너리 룰셋 적용
  (운영자 승격 게이트).

## 슬라이스 2 (라이브/페이퍼 실행 경로 — 일회성, paper 기본·돈 무이동) — 완료 ✅

라이브 워커 1Hz 틱 루프에 월 단위 재조정을 끼워 넣는 대신, **일회성 실행기**로
분리(더 안전·단순). 기존 OrderRouter + K1 게이트 체인 + paper/live 분기를 그대로
재사용한다(별도 돈 경로·커널 무터치). paper 기본, 실주문은 명시적 `--mode live` 필요.

- [x] **T009** `execution/rebalancer.py` 신규 — `execute_rebalance(...)`:
  저장 바로 합성 점수 → 목표 비중 → 보유·시세로 재조정 계획 → **필터 없는 합성 룰**로
  `router.submit_order` 라우팅(게이트·감사·paper/live 그대로). 각 주문 수량을 per-trade
  캡 한도로 클램프(하향 전용)해 큰 청산도 게이트 통과(반복 호출로 수렴). marketable LIMIT.
- [x] **T010** `tests/integration/test_spec_032_live_rebalancer.py` — paper 라우터 +
  주입 시세로 매수+매도 청산·게이트 통과·per-trade 클램프·결정론 검증.
- [x] **T011** `cli.py` — `rebalance-once` 명령(paper 기본, `--mode live` 명시 필요,
  text/json). 라이브는 운영자 명시 실행 시에만 실주문(돈 경로 — 운영자 게이트).

## ② 단계 — 측정: 단순 보유 벤치마크 비교 + 단일 잣대 정합 — 완료 ✅

운영자 "② 실제 데이터로 재조정 vs 현행 비교 측정" 지시. 컨테이너에 과거 데이터셋
없음 + 외부 데이터 네트워크 차단(403) → 실데이터 비교는 운영자의 `ingest-history`
선행 필요. 대신 **비교 측정 장치**를 백테스트에 내장(운영자가 실데이터만 적재하면 즉시
"재조정이 단순 보유를 이겼나"를 같은 잣대로 산출).

- [x] **T012** `backtest/portfolio_replay.py` — 균등가중 매수후보유 벤치마크 곡선 +
  `benchmark_total_return_pct`·`benchmark_max_drawdown_pct`·`benchmark_sharpe_ratio`·
  `excess_return_pct`(전략−벤치) 산출. `cli.py backtest-portfolio` 출력에 비교 표시.
- [x] **T013** 단일 잣대 정합 수정 — 백테스트 재조정도 per-trade 캡으로 **하향 클램프**
  (라이브 실행기와 동일). 이전엔 백테스트가 캡 초과 주문을 통째로 거부해 라이브(클램프)와
  어긋났음(헌법 X.2 위반). 이제 둘 다 클램프+반복 수렴. 신규/수정 테스트로 검증.
- [x] **T014** 시연(합성 3년·10종목·KIS 비용): 모든 재조정 스킴이 단순 보유(+17%)를
  초과(예: equal top4 +42.5%, 초과 +25.4%). **합성 데이터 = 방향성 시연**이며 실제
  수치는 운영자가 실데이터 적재 후 `auto-invest backtest-portfolio` 로 산출.
