# HANDOFF-141 — Broad No-Edge Cross-Asset Relative Value Contract

## 상태

#607이 main에 merge되어 `candidate-broad-no-edge-cross-asset-relative-value-experiment`가 스펙 135로 완료됐다. 이 작업은 돈을 움직이는 패치가 아니라, `NO_EDGE_YET` 상태에서 절대 모멘텀 반복을 멈추고 자산 간 상대가치 후보 축을 여는 no-live 운영 계약이다.

핵심 결론은 이렇다. 상대가치 계약은 현재 sidecar 기준 `CONTRACT_READY`이고, released-work는 이번 후보를 released 처리했다. autonomous-work는 수동 재실행 run `31891650370` 뒤 다음 후보 `candidate-broad-no-edge-tail-risk-convexity-experiment`를 골랐다. 실주문, live 재무장, 자본 배분은 여전히 금지다.

## 왜 했나

광역 no-edge 첫 파동은 자산군 확장, 다중 보유 기간·신호군, 레짐·비용, 데이터 결측 감사를 닫았다. 그래도 money-path는 `NO_EDGE_YET`다. 같은 절대 모멘텀 변형만 반복하면 돈을 벌 가능성이 있는 후보 공간이 좁아진다.

안전한 해결은 실거래 게이트를 여는 것이 아니라, `rebalance-paper-forward`, `public-data`, `regime-stratify`, `money-path`, `edge-autoarm`, `released-work`, `pipeline-liveness`를 함께 읽어 주식·채권·원자재·현금성 자산 간 상대가치 후보 축을 기계 판독 가능한 계약으로 남기는 것이다.

## 무엇을 고쳤나

- `specs/135-broad-no-edge-cross-asset-relative-value/` SDD 산출물을 추가했다.
- `src/auto_invest/analytics/broad_no_edge_cross_asset_relative_value.py`가 상대가치 no-live 계약을 JSON/Markdown으로 만든다.
- `scripts/broad_no_edge_cross_asset_relative_value_probe.py`가 sidecar 입력을 받아 계약을 발행한다.
- `tests/unit/test_broad_no_edge_cross_asset_relative_value.py`와 `tests/integration/test_broad_no_edge_cross_asset_relative_value_probe.py`가 ready, missing evidence, missing cash proxy, live-capable money path, manifest, JSON/Markdown 출력을 고정한다.
- `completed_candidate_id: candidate-broad-no-edge-cross-asset-relative-value-experiment` 완료 마커와 완료된 `tasks.md` 덕분에 released-work가 이번 후보를 소비한다.
- `.specify/feature.json`은 최신 완료 스펙 135를 가리킨다.

## 확인한 증거

- PR #607: `https://github.com/jinooaction/claude/pull/607`.
- 기능 커밋: `bda57ae`.
- merge commit: `2b95151d1cd63bc15b78f7fc56455f0319e46b0d`.
- GitHub PR quality gate: run `31891577659`, success.
- deploy-on-merge run: `31891597781`, commit `2b95151`, success.
- released-work run: `31891597802`, commit `2b95151`, released_count 54, 스펙 135 후보 released 포함.
- autonomous-work push run: `31891597778`, success였지만 released-work와 병렬 실행되어 이전 후보를 한 번 더 보았다.
- autonomous-work 수동 재실행 run: `31891650370`, commit `2b95151`, selected_work `candidate-broad-no-edge-tail-risk-convexity-experiment`, status `EXECUTION_READY`, risk_grade 2.
- 최신 relative-value sidecar 재현: `CONTRACT_READY`, completed candidate `candidate-broad-no-edge-cross-asset-relative-value-experiment`, next candidate `candidate-broad-no-edge-tail-risk-convexity-experiment`, lane 4개 모두 `PROPOSED`.
- 로컬 focused 검증: 8 passed, 52 deselected.
- 로컬 전체 검증: `uv run pytest` 2785 passed, 5 skipped.
- 로컬 린트: `uv run ruff check src tests scripts/broad_no_edge_cross_asset_relative_value_probe.py` 통과.
- 기타 검증: `git diff --check` 통과, `uv run python scripts/check_handoff_facts.py` OK, `uv run python scripts/agent_harness_probe.py --strict` OK(14/14), PR quality gate 통과.

## 안전 경계

이번 변경은 등급 2 운영 보정이다.

브로커 API 호출, 실제 주문, 실거래 전환, live 재무장, 자본 배분, 라이브 전략 설정, whitelist/caps, 손실 예산, KIS secret, 감사 로그, 헌법, kernel manifest는 바꾸지 않았다.

`money-path`는 여전히 `PREVIEW_ONLY` / `NO_EDGE_YET`이고, edge-autoarm은 `WAIT_EDGE` / `NO_EDGE`다. 실거래는 기존 엣지 확정과 운영자 승인 경계 없이는 열리지 않는다.

## 다음 세션 판단

현재 최신 autonomous-work selected_work는 `candidate-broad-no-edge-tail-risk-convexity-experiment`다. 다음 작업은 `regime-stratify`, `execution-quality`, `rebalance-paper-forward` 증거를 함께 읽어 tail-risk 방어 후보, 비용 부담, 레짐별 대기 조건을 no-live 계약으로 만드는 것이다.

주문 제출, live 재무장, 자본 배분은 하지 않는다. 현재 돈 경로는 여전히 `PREVIEW_ONLY`/`NO_EDGE_YET`이다.
