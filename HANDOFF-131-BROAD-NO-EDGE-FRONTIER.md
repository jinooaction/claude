# HANDOFF-131 — Broad NO_EDGE Frontier Completion

## 상태

#584가 main에 merge되어 broad no-edge parent 반복 억제와 `broad_no_edge_frontier_map`이 출시됐다. 이 closeout은 released-work가 #584의 완료 후보 `candidate-broad-frontier-expansion-no-edge-58298dfc172c`를 실제 완료로 읽게 하는 completion marker를 추가한다.

핵심 결론은 이렇다. 돈 경로를 강제로 열지 않고, `NO_EDGE_YET` 이후 멈춘 탐색을 다음 no-live 실험 후보로 전진시키는 장치가 들어갔다.

## 왜 했나

#582는 모든 알려진 후보가 닫히고도 `NO_EDGE_YET`이면 broad parent 후보를 발행했다. 하지만 parent 후보를 수행한 뒤 released-work 목록이 바뀌면 parent 지문이 새로 계산되어 같은 broad parent가 다시 생길 수 있었다.

또한 broad parent 자체는 "검토 범위를 넓혀라"는 일감이었지만, 수행 뒤에 어떤 no-live 실험 축부터 시작할지 보고서에 분리돼 있지 않았다.

## 무엇을 고쳤나

- broad no-edge parent 지문 입력에서 broad no-edge parent와 후속 후보 release를 제외했다.
- `broad_no_edge_frontier_map`을 JSON과 Markdown 보고에 추가했다.
- 지도는 네 축을 가진다: 자산군 확장과 방어 회전, 다중 보유 기간과 신호군, 레짐과 비용 견고성, 데이터 결측 원인 감사.
- parent 후보가 released-work에 닫힌 뒤 no-edge 증거가 유지되면 첫 다음 후보는 `candidate-broad-no-edge-asset-universe-rotation-experiment`다.
- 스펙 124에 `completed_candidate_id: candidate-broad-frontier-expansion-no-edge-58298dfc172c`를 남겨 released-work가 parent 후보를 닫을 수 있게 했다.

## 확인한 증거

- PR #584: `https://github.com/jinooaction/claude/pull/584`.
- 기능 커밋: `b863e0b`.
- merge commit: `bd36342072356f74bb53de4264565d2717cbe678`.
- deploy run: `31476005233`, `Deploy on merge to main`, success, commit `bd36342`.
- released-work run: `31476005722`, success, commit `bd36342`, released_count 42.
- autonomous-work run: `31476005231`, success, commit `bd36342`, selected candidate `candidate-broad-frontier-expansion-no-edge-58298dfc172c`.
- 로컬 released-work replay: completion marker 포함 시 released_count 43, `candidate-broad-frontier-expansion-no-edge-58298dfc172c` released.
- 로컬 autonomous-work replay: completion marker 포함 시 selected candidate `candidate-broad-no-edge-asset-universe-rotation-experiment`.
- 로컬 검증: `uv run pytest` 2720 passed, 5 skipped; `uv run ruff check src tests` 통과; `git diff --check` 통과; `agent_harness_probe.py --strict` OK(14/14); `check_handoff_facts.py` OK.

## 안전 경계

이번 변경은 등급 2 운영 루프 보정이다.

실제 주문, 실거래 전환, live 재무장, 자본 배분, 라이브 전략 설정, whitelist/caps, 손실 예산, KIS secret, 감사 로그, 헌법, kernel manifest는 바꾸지 않았다.

새 후속 후보도 no-live 실험 설계 후보일 뿐이다. `money-path`는 여전히 `PREVIEW_ONLY` / `NO_EDGE_YET`이고, edge-autoarm은 `WAIT_EDGE` / `NO_EDGE`다. 실거래는 기존 엣지 확정과 운영자 승인 경계 없이는 열리지 않는다.

## 다음 세션 판단

이 closeout이 main에 들어간 뒤 released-work와 autonomous-work가 다시 돌면 다음 실제 작업은 `candidate-broad-no-edge-asset-universe-rotation-experiment`다.

그 작업은 `public-data`, `rebalance-paper-forward`, `money-path`, `edge-autoarm`, `released-work`, `autonomous-work`를 함께 읽고, 주식·현금성·채권성·방어 자산군 대체 후보의 no-live 후보군과 제외 기준을 SDD로 정의해야 한다. 주문 제출, live 재무장, 자본 배분은 하지 않는다.
