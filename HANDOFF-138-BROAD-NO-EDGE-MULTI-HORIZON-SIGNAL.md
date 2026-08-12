# HANDOFF-138 — Broad No-Edge Multi-Horizon Signal Contract

## 상태

#599가 main에 merge되어 `candidate-broad-no-edge-multi-horizon-signal-experiment`가 스펙 131로 완료됐다. 이 작업은 돈을 움직이는 패치가 아니라, `NO_EDGE_YET` 상태에서 같은 신호와 같은 보유 기간만 반복하지 않도록 다음 no-live 실험 후보군을 넓히는 운영 계약이다.

핵심 결론은 이렇다. 광역 no-edge frontier에서 자산군 확장과 다중 보유 기간·신호군 두 축은 released 상태가 됐다. 자동 실행 루프의 다음 후보는 `candidate-broad-no-edge-regime-cost-robustness-experiment`이고, 해야 할 일은 레짐 구간과 비용 민감도 기준을 no-live 계약으로 정의하는 것이다. 실주문, live 재무장, 자본 배분은 여전히 금지다.

## 왜 했나

이전 broad no-edge 작업은 "같은 자산군 안에서 조금 다른 신호만 다시 돌리는" 반복을 줄였다. 하지만 보유 기간과 신호군이 좁으면 여전히 비슷한 실패를 다른 이름으로 반복할 수 있다.

안전한 해결은 기준을 낮춰 실거래를 여는 것이 아니다. forward paper, money-path, edge-autoarm, public-data, regime-stratify, released-work, evolution-ledger, pipeline-liveness를 함께 읽어 단기·중기·장기 후보를 분리하고, 다음 검증 축을 기계 판독 가능한 no-live 계약으로 남기는 것이다.

## 무엇을 고쳤나

- `specs/131-broad-no-edge-multi-horizon-signal/` SDD 산출물을 추가했다.
- `src/auto_invest/analytics/broad_no_edge_multi_horizon_signal.py`가 다중 보유 기간·신호군 no-live 계약을 JSON/Markdown으로 만든다.
- `scripts/broad_no_edge_multi_horizon_signal_probe.py`가 sidecar 입력을 받아 계약을 발행한다.
- `tests/unit/test_broad_no_edge_multi_horizon_signal.py`와 `tests/integration/test_broad_no_edge_multi_horizon_signal_probe.py`가 계약 상태, 안전 경계, CLI 출력을 고정한다.
- `tests/unit/test_autonomous_work_execution.py`가 다중 horizon 후보 released 뒤 다음 broad no-edge 후보가 `candidate-broad-no-edge-regime-cost-robustness-experiment`로 전진하는 회귀를 고정한다.
- `completed_candidate_id: candidate-broad-no-edge-multi-horizon-signal-experiment` 완료 마커와 완료된 `tasks.md` 덕분에 released-work가 이번 후보를 소비한다.
- `.specify/feature.json`과 `CLAUDE.md`는 최신 완료 스펙 131을 가리킨다.

## 확인한 증거

- PR #599: `https://github.com/jinooaction/claude/pull/599`.
- 기능 커밋: `697c4d9`.
- merge commit: `012cdf04a71b012b8c5aa47d7c552a939a6e7e74`.
- GitHub PR quality gate: runs `31578375942`, `31578436259`, `31578436835`, all success.
- deploy-on-merge run: `31578457648`, commit `012cdf0`, success. 컨테이너에서 Actions run success는 확인했지만 서버 audit_log는 운영자 또는 서버 접근 표면에서만 확인할 수 있다.
- released-work run: `31578457879`, commit `012cdf0`, released_count 50, 스펙 131 후보 released 포함.
- autonomous-work run: `31578457715`, commit `012cdf0`, selected_work `candidate-broad-no-edge-regime-cost-robustness-experiment`, status `EXECUTION_READY`, risk_grade 2.
- 최신 multi-horizon sidecar 재현: `CONTRACT_READY`, proposed_count 4, waiting_count 0, release_gate PASS, regime_gate PASS.
- local released-work/autonomous-work 재현: multi-horizon child released, broad no-edge frontier map에서 asset-universe와 multi-horizon은 released, regime-cost와 data-gap-audit은 open, 다음 selected_work는 `candidate-broad-no-edge-regime-cost-robustness-experiment`.
- 로컬 전체 검증: `uv run pytest` 2759 passed, 5 skipped.
- 로컬 린트: `uv run ruff check src tests` 통과.
- 기타 검증: `git diff --check` 통과, `uv run python scripts/check_handoff_facts.py` OK, `uv run python scripts/agent_harness_probe.py --strict` OK(14/14), PR quality gate 통과.

## 안전 경계

이번 변경은 등급 2 운영 보정이다.

브로커 API 호출, 실제 주문, 실거래 전환, live 재무장, 자본 배분, 라이브 전략 설정, whitelist/caps, 손실 예산, KIS secret, 감사 로그, 헌법, kernel manifest는 바꾸지 않았다.

`money-path`는 여전히 `PREVIEW_ONLY` / `NO_EDGE_YET`이고, edge-autoarm은 `WAIT_EDGE` / `NO_EDGE`다. 실거래는 기존 엣지 확정과 운영자 승인 경계 없이는 열리지 않는다.

## 다음 세션 판단

현재 최신 autonomous-work selected_work는 `candidate-broad-no-edge-regime-cost-robustness-experiment`다.

다음 작업은 `regime-stratify`, `execution-quality`, `money-path` 증거를 함께 읽어 레짐 구간별 통과 기준과 비용 민감도 stress test를 no-live 계약으로 정의하는 것이다.

주문 제출, live 재무장, 자본 배분은 하지 않는다. 현재 돈 경로는 여전히 `PREVIEW_ONLY`/`NO_EDGE_YET`이다.
