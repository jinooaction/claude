# 스펙 036 — 작업 (tasks)

전부 완료. Kernel 터치 0건, 돈 0 이동, 기존 동작 보존(옵트인).

- [x] **T01** 순수 모듈 `strategy/trend.py` — `TrendSpec`·`above_trend`·`apply_trend_filter`
  (sma / absolute_momentum, 재정규화 없음, on_insufficient 정책). (FR-T01, FR-T02)
- [x] **T02** `target_weights(..., trend=...)` 옵트인 인자 + `_base_weights` 추출. None 이면 byte
  동일. (FR-T03)
- [x] **T03** `config/rules.py` `TrendFilterConfig` + `PortfolioRebalanceConfig.trend_filter`(옵트인).
  (FR-T04)
- [x] **T04** 호출부 배선: `execution/rebalancer.py`(`_trend_spec`) + `backtest/portfolio_replay.py`.
  (FR-T05)
- [x] **T05** 단위 테스트 `tests/unit/test_trend_filter.py` — 추세 판정·필터·spec 검증·config
  라운드트립·target_weights 통합 (20건). (SC-T01~T03, SC-T05~T06)
- [x] **T06** 통합 테스트 `tests/integration/test_spec_036_trend_filter.py` — 합성 폭락에서 필터
  ON 의 최대낙폭 < OFF, 필터 미설정 회귀 (2건). (SC-T04)
- [x] **T07** 예시 설정 `specs/036-trend-filter/example-trend-portfolio.toml`.
- [x] **T08** 전체 테스트(1475 통과·4 스킵)·린트(All checks passed) 확인.

## 검증 메모

- 전체 `uv run pytest`: 1475 passed, 4 skipped(라이브 KIS 게이트). 신규 22건(단위 20 + 통합 2).
- 린트 `uv run ruff check src tests`: All checks passed.
- 메커니즘 시연(합성 120세션 상승 후 60세션 −55% 폭락, top_n=2 equal): 추세 필터(sma 40) ON 이
  OFF 보다 최대낙폭이 엄격히 작음 = 폭락에서 현금 이탈이 실제로 작동. (엣지 주장 아님 — stale.)
