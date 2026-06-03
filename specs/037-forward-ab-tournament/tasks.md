# 스펙 037 — 작업 (tasks)

전부 완료. Kernel 터치 0건, 코드 변경 0(설정+워크플로+테스트만), 돈 0 이동.

- [x] **T01** 대조군 설정 `deploy/canary-portfolio-notrend.toml` — ON 과 trend_filter 외 전부
  동일(생성 시 자동 검증). (FR-A01)
- [x] **T02** 워크플로 `rebalance-paper-forward.yml` 2팔 재구성 — 전용 DB(forward_trend.db /
  forward_notrend.db), 각 팔 backfill→rebalance→nav-snapshot→forward-verdict, PAPER 전용. (FR-A02)
- [x] **T03** 사이드카 두 판정 나란히 발행 + 준비 로그. (FR-A03)
- [x] **T04** 회귀 테스트 `tests/unit/test_canary_portfolio_config.py` — 대조군 동일성(추세
  필터만 차이) + 기존 ON 설정 검증 (3건). (FR-A04, SC-A01)
- [x] **T05** YAML 유효성 + 전체 테스트 + 린트 확인. (SC-A02, SC-A03)

## 검증 메모

- YAML: `yaml.safe_load` OK, jobs=[forward-paper], steps=7.
- 대조군 동일성: 유니버스·가중치·top_n·rebalance_mode·invested_fraction·주기·lookback·
  momentum 전부 ON 과 일치, trend_filter 만 None(테스트로 못박음).
- 전체 `uv run pytest`: 통과. 린트 `ruff check src tests`: All checks passed.
