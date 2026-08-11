# HANDOFF-130 — Broad Frontier Expansion After NO_EDGE Exhaustion

## 상태

완료. PR #582가 main에 merge됐고, post-merge `autonomous-work-execution` sidecar가 새 코드로 자동 실행되어 `wait-for-fresh-evidence` 대신 `candidate-broad-frontier-expansion-no-edge-58298dfc172c`를 선택했다.

결론은 단순하다. 지금 돈 경로가 막힌 이유는 브로커 연결이나 주문 경로가 아니라 검증된 투자 엣지가 아직 없기 때문이다. 그래서 안전장치를 우회하지 않고, 정적 후보 목록 밖의 no-live 투자 frontier를 더 넓게 찾는 후보를 자동으로 발행하게 했다.

## 왜 했나

기존 루프는 모든 알려진 macro, frontier, nested 후보가 released-work로 닫히고 retryable 검증 패키지도 남지 않으면 `OBSERVATION_WAIT` / `wait-for-fresh-evidence`로 떨어졌다.

이 판단은 닫힌 후보를 다시 고르지 않는다는 점에서는 안전했지만, `PREVIEW_ONLY` / `NO_EDGE_YET`가 계속되는 상태에서는 너무 좁았다. 운영자가 지적한 대로 같은 후보 목록 안에서 새 증거만 기다리면 앞으로도 같은 결론을 반복할 수 있다.

## 무엇을 고쳤나

- `src/auto_invest/analytics/autonomous_work_execution.py`에 fingerprint 기반 광역 frontier 후보를 추가했다.
- retryable 검증 실패 패키지가 남으면 `candidate-broad-frontier-expansion-validation-failures-<fingerprint>`를 발행한다.
- 검증 실패 패키지가 없어도 money-path / edge-autoarm이 `PREVIEW_ONLY`, `NO_EDGE_YET`, `NO_EDGE`, `WAIT_EDGE`, `ACCUMULATING_EDGE`이면 `candidate-broad-frontier-expansion-no-edge-<fingerprint>`를 발행한다.
- 같은 fingerprint가 released-work에 이미 있으면 다시 발행하지 않고 기다린다.
- 스펙 120의 요구사항, contract, tasks에 이 후속 조건을 남겼다.
- 단위 테스트는 blocked-package 갈래, no-edge 갈래, 같은 fingerprint 반복 억제를 검증한다.

## 확인한 증거

- PR #582: `https://github.com/jinooaction/claude/pull/582`.
- 기능 커밋: `2b0bda6`.
- merge commit: `a2c70707dec4b3da128686b6a6e1487ffad0d8e4`.
- deploy run: `31457946033`, `Deploy on merge to main`, success, commit `a2c7070`.
- released-work run: `31457946073`, success, commit `a2c7070`, released_count 42.
- autonomous-work run: `31457946057`, success, commit `a2c7070`, selected candidate `candidate-broad-frontier-expansion-no-edge-58298dfc172c`, status `EXECUTION_READY`.
- money-gate-alignment run: `31458045029`, success, selected_work_candidate `candidate-broad-frontier-expansion-no-edge-58298dfc172c`, overall `ALIGNED_WAITING`.
- pipeline-liveness run: `31458092515`, success, overall `OK`; autonomous-work, released-work, money-gate-alignment 모두 신선.
- 로컬 검증: `uv run pytest` 2717 passed, 5 skipped; `uv run ruff check src tests` 통과; `git diff --check` 통과; `agent_harness_probe.py --strict` OK(14/14); `check_handoff_facts.py`는 #582 merge 전 OK였고, 이 handoff 갱신 전 main 기준 전체 테스트는 HANDOFF stale 때문에 하네스 테스트 2개만 실패했다.

## 안전 경계

이번 변경은 등급 2 운영 루프 보정이다.

실제 주문, 실거래 전환, live 재무장, 자본 배분, 라이브 전략 설정, whitelist/caps, 손실 예산, KIS secret, 감사 로그, 헌법, kernel manifest는 바꾸지 않았다.

새 후보는 no-live 실험 축을 정의하는 Codex 작업 후보일 뿐이다. `money-path`는 여전히 `PREVIEW_ONLY` / `NO_EDGE_YET`이고, edge-autoarm은 `WAIT_EDGE` / `NO_EDGE`다. 실거래는 기존 엣지 확정과 운영자 승인 경계 없이는 열리지 않는다.

## 다음 세션 판단

다음 실제 작업은 `candidate-broad-frontier-expansion-no-edge-58298dfc172c`를 수행하는 것이다. 시작할 때는 `rebalance-paper-forward`, `money-path`, `edge-autoarm`, `public-data`, `regime-stratify`, `execution-quality`, `released-work`, `autonomous-work`를 함께 읽어야 한다.

검토 축은 전략군, 신호군, 보유 기간, 자산군, 레짐 구간, 비용 민감도, 데이터 결측 원인을 모두 포함한다. 단, 이 작업도 no-live 설계와 검증 후보 생성까지다. 주문 제출, live 재무장, 자본 배분은 하지 않는다.
