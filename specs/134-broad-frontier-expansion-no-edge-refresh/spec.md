# Feature Specification: Broad Frontier Expansion NO_EDGE Refresh

**Feature Branch**: `codex/broad-frontier-expansion-no-edge-refresh`
**Created**: 2026-08-15
**Status**: Draft
**Input**: User asked to use the goal skill and build the environment for earning money as fast as safely possible.

## User Scenarios & Testing

### User Story 1 - 이미 닫힌 broad no-edge 지도를 반복하지 않는다 (Priority: P1)

운영자는 broad no-edge 1차 후보 네 개가 모두 released 된 뒤에도 같은 parent 후보가 새 지문으로 반복 선택되지 않기를 원한다.

**Why this priority**: 반복 parent는 실제 돈 경로를 앞으로 밀지 못한다. 완료된 분석을 다시 여는 대신 다음 검증 가능한 no-live 후보가 나와야 한다.

**Independent Test**: released-work에 broad no-edge parent와 1차 네 후보가 모두 있을 때 autonomous-work가 새 parent 대신 2차 broad no-edge 후보를 선택한다.

### User Story 2 - 다음 no-live 투자 후보를 더 구체적으로 발행한다 (Priority: P2)

운영자는 `NO_EDGE_YET`가 계속될 때 새 장 데이터만 기다리지 않고, 상대가치, 꼬리위험 방어, 변동성 목표 같은 다음 탐색 축을 보고 싶다.

**Why this priority**: 실주문을 열 수 없을 때 가장 빠른 안전 경로는 기준을 낮추는 것이 아니라 검증 후보 공간을 넓히는 것이다.

**Independent Test**: 첫 2차 후보가 released 되면 다음 2차 후보가 순서대로 선택되고, 모든 2차 후보가 닫히면 `wait-for-fresh-evidence`로 내려간다.

### User Story 3 - 안전 경계를 유지한다 (Priority: P3)

운영자는 돈을 벌고 싶지만, 이번 작업이 실주문·자본 배분·live 재무장으로 해석되면 안 된다.

**Independent Test**: 새 work packet의 `safety_boundary`와 markdown 보고에 실제 주문, 자본 배분, live 재무장 금지가 남아 있다.

## Requirements

- **FR-001**: System MUST stop re-emitting `candidate-broad-frontier-expansion-no-edge-<fingerprint>` once any broad no-edge parent candidate is released.
- **FR-002**: System MUST extend `broad_no_edge_frontier_map` with second-wave no-live candidates after asset universe, multi-horizon signal, regime-cost robustness, and data-gap audit are released.
- **FR-003**: Second-wave candidates MUST include cross-asset relative value, tail-risk convexity, and volatility-target drawdown control.
- **FR-004**: System MUST emit the first unreleased second-wave candidate while current evidence remains `PREVIEW_ONLY`, `NO_EDGE_YET`, `NO_EDGE`, `WAIT_EDGE`, or `ACCUMULATING_EDGE`.
- **FR-005**: System MUST NOT modify broker API calls, order routing, capital allocation, live strategy settings, whitelist/caps, secrets, constitution, or kernel files.
- **FR-006**: Released-work MUST be able to close this work with `completed_candidate_id: candidate-broad-frontier-expansion-no-edge-122eb31c06bd`.

## Success Criteria

- **SC-001**: Focused autonomous-work tests prove a released broad no-edge parent does not reappear as a new parent.
- **SC-002**: Focused tests prove second-wave broad no-edge candidates advance in deterministic order.
- **SC-003**: Full validation passes before merge: `uv run pytest`, `uv run ruff check src tests`, `git diff --check`, `uv run python scripts/check_handoff_facts.py`, and `uv run python scripts/agent_harness_probe.py --strict`.
- **SC-004**: PR body passes `scripts/check_pr_quality_gate.py`.

## Assumptions

- Latest money path remains `PREVIEW_ONLY` / `NO_EDGE_YET`.
- This is risk grade 2 because it changes autonomous candidate selection and reporting only.
- Faster safe progress means more useful no-live candidates, not lowering the live-money gate.
