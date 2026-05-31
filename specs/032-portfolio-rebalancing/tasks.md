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
