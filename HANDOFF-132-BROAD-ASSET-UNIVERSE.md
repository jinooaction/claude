# HANDOFF-132 — Broad NO_EDGE Asset Universe Contract

## 상태

#587이 main에 merge되어 `candidate-broad-no-edge-asset-universe-rotation-experiment`가 스펙 125로 완료됐다. 이 작업은 돈을 움직이는 패치가 아니라, `NO_EDGE_YET` 뒤 다음 no-live 실험 후보를 더 넓고 안전하게 고르는 계약이다.

핵심 결론은 이렇다. 이미 실패한 단순 wide 확장을 반복하지 않고, 현금성·국채 만기·인플레이션·달러 충격 방어 후보를 기계 판독 보고서로 분리했다.

## 왜 했나

최근 forward 토너먼트는 비교 가능한 7개 트랙이 모두 `NO_EDGE`였다. 특히 `wide` 트랙은 `SPY`, `QQQ`, `EFA`, `EEM`, `IEF`, `TLT`, `LQD`, `GLD`, `DBC`, `VNQ`, `UUP` 11개 슬리브를 이미 시험했지만 엣지가 없었다.

따라서 다음 작업은 자산을 더 많이 넣는 반복이 아니라, 방어 역할이 다른 후보를 분리하고 어떤 후보는 제외해야 하는지 명확히 남기는 것이어야 했다.

## 무엇을 고쳤나

- `specs/125-broad-no-edge-asset-universe/` SDD 산출물을 추가했다.
- `src/auto_invest/analytics/broad_no_edge_asset_universe_rotation.py`가 7개 sidecar를 읽어 JSON/Markdown 계약을 만든다.
- 보고서는 forward universe를 자산군 bucket으로 분해하고, tested bucket count, incumbent bucket, wide track status, 후보 수, 제외 수를 계산한다.
- 제안 후보는 `cash_treasury_defense_rotation`, `duration_barbell_defense_rotation`, `inflation_shock_defense_rotation`, `currency_shock_defense_rotation`이다.
- 제외 기준은 `repeat_wide_universe_static`과 `live_rearm_or_order_submission`이다.
- `scripts/broad_no_edge_asset_universe_rotation_probe.py`가 manifest, JSON 출력, Markdown 출력, repo-root released-work override를 제공한다.
- 스펙 125 contract에 `completed_candidate_id: candidate-broad-no-edge-asset-universe-rotation-experiment`와 `next_candidate_id: candidate-broad-no-edge-multi-horizon-signal-experiment`를 남겼다.

## 확인한 증거

- PR #587: `https://github.com/jinooaction/claude/pull/587`.
- 기능 커밋: `bb187c9`.
- merge commit: `97019654a92f77bd2ebe09abf7c1b17dbf698573`.
- GitHub PR quality gate: run `31479598247`, success.
- released-work run: `31479754566`, commit `9701965`, released_count 44, 스펙 125 후보 released 포함.
- 최신 autonomous-work sidecar: commit `9701965`, timestamp `2026-08-11T09:53:55Z`, overall_status `EXECUTION_READY`.
- broad frontier local replay: asset-universe 후보 `coverage_status=released`, multi-horizon 후보 `coverage_status=open`.
- 로컬 focused 검증: 7 passed.
- 로컬 전체 검증: `uv run pytest` 2727 passed, 5 skipped.
- 로컬 린트: `uv run ruff check src tests` 통과.
- 기타 검증: `git diff --check` 통과, `uv run python scripts/check_handoff_facts.py` OK, `uv run python scripts/agent_harness_probe.py --strict` OK(14/14), PR quality gate 통과.

## 안전 경계

이번 변경은 등급 2 운영 보고와 candidate closure 보정이다.

실제 주문, 실거래 전환, live 재무장, 자본 배분, 라이브 전략 설정, whitelist/caps, 손실 예산, KIS secret, 감사 로그, 헌법, kernel manifest는 바꾸지 않았다.

`money-path`는 여전히 `PREVIEW_ONLY` / `NO_EDGE_YET`이고, edge-autoarm은 `WAIT_EDGE` / `NO_EDGE`다. 실거래는 기존 엣지 확정과 운영자 승인 경계 없이는 열리지 않는다.

## 다음 세션 판단

전체 autonomous-work 최신 selected_work는 현재 더 높은 우선순위의 `candidate-broad-frontier-expansion-validation-failures-22f38b8629eb`다.

다만 broad no-edge frontier 안에서는 스펙 125가 닫혔고, 다음 열린 broad 후보는 `candidate-broad-no-edge-multi-horizon-signal-experiment`다. 이 후보를 이어갈 때는 `rebalance-paper-forward`, `learning ledger`, `money-path`, `edge-autoarm`, `public-data`를 함께 읽어 단기·중기·장기 보유 기간과 trend·carry·quality·volatility 신호군을 분리해야 한다.
