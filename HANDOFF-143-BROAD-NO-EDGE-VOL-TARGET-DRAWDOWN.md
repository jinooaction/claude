# HANDOFF-143 — Broad No-Edge Vol-Target Drawdown Contract

## 상태

#611이 main에 merge되어 `candidate-broad-no-edge-vol-target-drawdown-experiment`가 스펙 137로 완료됐다. 이 작업은 돈을 움직이는 패치가 아니라, `NO_EDGE_YET` 상태에서 변동성 목표와 낙폭 제어가 확률 신뢰도를 올릴 수 있는지 분리하는 no-live 운영 계약이다.

핵심 결론은 이렇다. vol-target drawdown 계약은 현재 sidecar 기준 `CONTRACT_READY`이고, released-work는 이번 후보를 released 처리했다. 최신 autonomous-work는 `wait-for-fresh-evidence` / `OBSERVATION_WAIT`다. 실주문, live 재무장, 자본 배분은 여전히 금지다.

## 왜 했나

광역 no-edge 2차 후보에서 자산 간 상대가치와 꼬리위험 방어·볼록성까지 닫혔지만 money-path는 아직 `NO_EDGE_YET`다. 같은 평균 수익률 후보만 반복하면 후보 공간이 좁아진다.

안전한 해결은 실거래 게이트를 여는 것이 아니라, `rebalance-paper-forward`, `regime-stratify`, `execution-quality`, `money-path`, `edge-autoarm`, `released-work`, `pipeline-liveness`를 함께 읽어 변동성 목표·낙폭 제어 후보와 자본 사다리 제외 조건을 기계 판독 가능한 계약으로 남기는 것이다.

## 무엇을 고쳤나

- `specs/137-broad-no-edge-vol-target-drawdown/` SDD 산출물을 추가했다.
- `src/auto_invest/analytics/broad_no_edge_vol_target_drawdown.py`가 변동성 목표·낙폭 제어 no-live 계약을 JSON/Markdown으로 만든다.
- `scripts/broad_no_edge_vol_target_drawdown_probe.py`가 sidecar 입력을 받아 계약을 발행한다.
- `tests/unit/test_broad_no_edge_vol_target_drawdown.py`와 `tests/integration/test_broad_no_edge_vol_target_drawdown_probe.py`가 ready, missing evidence, live-capable money path, manifest, JSON/Markdown 출력을 고정한다.
- 계약은 `volatility_target_scaling`, `drawdown_deleveraging_overlay`, `psr_sensitivity_hurdle`, `live_drawdown_exclusion`, `broad_no_edge_vol_target_context` 5개 lane을 만든다.
- `completed_candidate_id: candidate-broad-no-edge-vol-target-drawdown-experiment` 완료 마커와 완료된 `tasks.md` 덕분에 released-work가 이번 후보를 소비한다.
- `.specify/feature.json`은 최신 완료 스펙 137을 가리킨다.

## 확인한 증거

- PR #611: `https://github.com/jinooaction/claude/pull/611`.
- 기능 커밋: `bae22b3`.
- merge commit: `0505e84b6fb9c7274065a78d7ec92e68b8c52715`.
- GitHub PR quality gate: run `31912155500`, success.
- deploy-on-merge run: `31912195904`, commit `0505e84`, success.
- released-work run: `31912195901`, commit `0505e84`, released_count 56, 스펙 137 후보 released 포함.
- autonomous-work run: `31912233910`, commit `0505e84`, selected_work `wait-for-fresh-evidence`, status `OBSERVATION_WAIT`.
- 최신 vol-target drawdown sidecar 재현: `CONTRACT_READY`, completed candidate `candidate-broad-no-edge-vol-target-drawdown-experiment`, next candidate `wait-for-fresh-evidence`, lane 5개 모두 `PROPOSED`.
- 로컬 focused 검증: 60 passed.
- 로컬 전체 검증: `uv run pytest` 2799 passed, 5 skipped.
- 로컬 린트: `uv run ruff check src tests` 통과.
- 기타 검증: `git diff --check` 통과, `uv run python scripts/check_handoff_facts.py` OK, `uv run python scripts/agent_harness_probe.py --strict` OK(14/14), PR quality gate 통과.

## 안전 경계

이번 변경은 등급 2 운영 보정이다.

브로커 API 호출, 실제 주문, 실거래 전환, live 재무장, 자본 배분, 라이브 전략 설정, whitelist/caps, 손실 예산, KIS secret, 감사 로그, 헌법, kernel manifest는 바꾸지 않았다.

`money-path`는 여전히 `PREVIEW_ONLY` / `NO_EDGE_YET`이고, edge-autoarm은 `WAIT_EDGE` / `NO_EDGE`다. 실거래는 기존 엣지 확정과 운영자 승인 경계 없이는 열리지 않는다.

## 다음 세션 판단

현재 최신 autonomous-work selected_work는 `wait-for-fresh-evidence`다. 실행 가능한 후보, 운영자 승인 필요 후보, 복구 우선 후보가 없고, 현재 보이는 후보는 완료 8개와 억제 2개뿐이다.

다음 세션은 새 scheduled sidecar가 쌓인 뒤 `money-path`, `edge-autoarm`, `capital-path-readiness`, `autonomous-work`, `released-work`를 다시 읽어 `NO_EDGE_YET` 또는 `OBSERVATION_WAIT`가 바뀌었는지 확인해야 한다.

주문 제출, live 재무장, 자본 배분은 하지 않는다. 현재 돈 경로는 여전히 `PREVIEW_ONLY`/`NO_EDGE_YET`이다.
