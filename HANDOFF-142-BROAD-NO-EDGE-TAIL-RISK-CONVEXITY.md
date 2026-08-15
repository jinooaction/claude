# HANDOFF-142 — Broad No-Edge Tail-Risk Convexity Contract

## 상태

#609가 main에 merge되어 `candidate-broad-no-edge-tail-risk-convexity-experiment`가 스펙 136으로 완료됐다. 이 작업은 돈을 움직이는 패치가 아니라, `NO_EDGE_YET` 상태에서 평균 수익률 후보 반복을 줄이고 큰 하락장 방어·볼록성 후보 축을 여는 no-live 운영 계약이다.

핵심 결론은 이렇다. tail-risk convexity 계약은 현재 sidecar 기준 `CONTRACT_READY`이고, released-work는 이번 후보를 released 처리했다. autonomous-work는 다음 후보 `candidate-broad-no-edge-vol-target-drawdown-experiment`를 골랐다. 실주문, live 재무장, 자본 배분은 여전히 금지다.

## 왜 했나

자산군 확장, 다중 보유 기간, 레짐·비용, 데이터 결측, 자산 간 상대가치까지 닫혔지만 money-path는 아직 `NO_EDGE_YET`다. 같은 평균 수익률 후보만 반복하면 후보 공간이 좁아진다.

안전한 해결은 실거래 게이트를 여는 것이 아니라, `rebalance-paper-forward`, `regime-stratify`, `execution-quality`, `money-path`, `edge-autoarm`, `released-work`, `pipeline-liveness`를 함께 읽어 꼬리위험 방어 후보와 비용 부담 제외 조건을 기계 판독 가능한 계약으로 남기는 것이다.

## 무엇을 고쳤나

- `specs/136-broad-no-edge-tail-risk-convexity/` SDD 산출물을 추가했다.
- `src/auto_invest/analytics/broad_no_edge_tail_risk_convexity.py`가 꼬리위험 방어·볼록성 no-live 계약을 JSON/Markdown으로 만든다.
- `scripts/broad_no_edge_tail_risk_convexity_probe.py`가 sidecar 입력을 받아 계약을 발행한다.
- `tests/unit/test_broad_no_edge_tail_risk_convexity.py`와 `tests/integration/test_broad_no_edge_tail_risk_convexity_probe.py`가 ready, missing evidence, missing tail regime, live-capable money path, manifest, JSON/Markdown 출력을 고정한다.
- `completed_candidate_id: candidate-broad-no-edge-tail-risk-convexity-experiment` 완료 마커와 완료된 `tasks.md` 덕분에 released-work가 이번 후보를 소비한다.
- `.specify/feature.json`은 최신 완료 스펙 136을 가리킨다.

## 확인한 증거

- PR #609: `https://github.com/jinooaction/claude/pull/609`.
- 기능 커밋: `7c1ce01`.
- merge commit: `28c6f747cf309684f8c1d93610accbc44fd0aceb`.
- GitHub PR quality gate: run `31893364400`, success.
- deploy-on-merge run: `31893402719`, commit `28c6f74`, success.
- released-work run: `31893402757`, commit `28c6f74`, released_count 55, 스펙 136 후보 released 포함.
- autonomous-work run: `31893402789`, commit `28c6f74`, selected_work `candidate-broad-no-edge-vol-target-drawdown-experiment`, status `EXECUTION_READY`, risk_grade 2.
- 최신 tail-risk sidecar 재현: `CONTRACT_READY`, completed candidate `candidate-broad-no-edge-tail-risk-convexity-experiment`, next candidate `candidate-broad-no-edge-vol-target-drawdown-experiment`, lane 5개 모두 `PROPOSED`.
- 로컬 focused 검증: 14 passed, 46 deselected.
- 로컬 전체 검증: `uv run pytest` 2792 passed, 5 skipped.
- 로컬 린트: `uv run ruff check src tests` 통과.
- 기타 검증: `git diff --check` 통과, `uv run python scripts/check_handoff_facts.py` OK, `uv run python scripts/agent_harness_probe.py --strict` OK(14/14), PR quality gate 통과.

## 안전 경계

이번 변경은 등급 2 운영 보정이다.

브로커 API 호출, 실제 주문, 실거래 전환, live 재무장, 자본 배분, 라이브 전략 설정, whitelist/caps, 손실 예산, KIS secret, 감사 로그, 헌법, kernel manifest는 바꾸지 않았다.

`money-path`는 여전히 `PREVIEW_ONLY` / `NO_EDGE_YET`이고, edge-autoarm은 `WAIT_EDGE` / `NO_EDGE`다. 실거래는 기존 엣지 확정과 운영자 승인 경계 없이는 열리지 않는다.

## 다음 세션 판단

현재 최신 autonomous-work selected_work는 `candidate-broad-no-edge-vol-target-drawdown-experiment`다. 다음 작업은 `money-path`, `edge-autoarm`, forward verdict, live drawdown evidence를 함께 읽어 변동성 목표·낙폭 제어 no-live 후보와 자본 사다리로 올릴 수 없는 제외 조건을 정의하는 것이다.

주문 제출, live 재무장, 자본 배분은 하지 않는다. 현재 돈 경로는 여전히 `PREVIEW_ONLY`/`NO_EDGE_YET`이다.
