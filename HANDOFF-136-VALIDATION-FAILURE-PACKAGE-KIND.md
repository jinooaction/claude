# HANDOFF-136 — Validation Failure Package-Kind Expansion Contract

## 상태

#595가 main에 merge되어 `candidate-broad-validation-failure-package-kind-expansion-contract`가 스펙 129로 완료됐다. 이 작업은 돈을 움직이는 패치가 아니라, 검증 실패 child 후보의 실패 구조를 패키지 종류별로 나눠 다음 no-live 후보 축을 넓힌 운영 보정이다.

핵심 결론은 이렇다. 데이터 준비도는 이미 통과했으므로, 이제 실패를 한 덩어리로 재시도하지 않는다. `strategy_backtest`와 `portfolio_backtest`를 분리했고, released-work가 이번 후보를 소비한 뒤 자율 작업 루프는 다음 child `candidate-broad-validation-failure-promotion-recheck-contract`로 전진했다.

## 왜 했나

스펙 128은 검증 실패 패키지 2개가 데이터 결측 때문이 아니라는 점을 닫았다. 하지만 그 다음에도 실패를 단순히 "검증 실패"로만 보면 같은 후보를 반복하거나, 전략 문제와 포트폴리오 구성 문제를 섞어서 보게 된다.

안전한 해결은 실패 명령을 무작정 다시 실행하거나 실거래 기준을 낮추는 것이 아니다. candidate-packages와 candidate-results를 읽어 패키지 종류별 bucket, 실행 지표, 제한된 출력 힌트, 다음 no-live 실험 축을 기계 판독 가능한 계약으로 남기는 것이다.

## 무엇을 고쳤나

- `specs/129-validation-failure-package-kind-expansion/` SDD 산출물을 추가했다.
- `src/auto_invest/analytics/validation_failure_package_kind_expansion.py`가 검증 실패 패키지 종류별 확장 계약을 JSON/Markdown으로 만든다.
- `scripts/validation_failure_package_kind_expansion_probe.py`가 sidecar 입력을 받아 계약을 발행한다.
- `tests/unit/test_validation_failure_package_kind_expansion.py`가 strategy/portfolio 분리, 지표 보존, 증거 누락 상태, 안전 경계를 고정한다.
- `tests/unit/test_autonomous_work_execution.py`가 package-kind 후보 released 뒤 `candidate-broad-validation-failure-promotion-recheck-contract`로 전진하는 회귀를 고정한다.
- `completed_candidate_id: candidate-broad-validation-failure-package-kind-expansion-contract` 완료 마커와 완료된 `tasks.md` 덕분에 released-work가 이번 후보를 소비한다.
- `.specify/feature.json`과 `CLAUDE.md`는 최신 완료 스펙 129를 가리킨다.

## 확인한 증거

- PR #595: `https://github.com/jinooaction/claude/pull/595`.
- 기능 커밋: `bc473ec`.
- merge commit: `027b34f23b3f3f86d5741c5562d2281f6e244490`.
- GitHub PR quality gate: runs `31566919408`, `31567029010`, both success.
- released-work run: `31567052065`, commit `027b34f`, released_count 48, 스펙 129 후보 released 포함.
- autonomous-work run: `31567052426`, commit `027b34f`, selected_work `candidate-broad-validation-failure-promotion-recheck-contract`, status `EXECUTION_READY`, risk_grade 2.
- deploy-on-merge run: `31567052052`, success. 컨테이너에서 Actions run success는 확인했지만 서버 audit_log는 운영자 또는 서버 접근 표면에서만 확인할 수 있다.
- 최신 package-kind sidecar 재현: `CONTRACT_READY`, package_count 2, bucket_count 2, retryable_count 2, command_count 4, execution_evidence_count 4.
- local released-work/autonomous-work 재현: released_count 48, package-kind child released, promotion-recheck child open and selected.
- 로컬 전체 검증: `uv run pytest` 2744 passed, 5 skipped.
- 로컬 린트: `uv run ruff check src tests` 통과.
- 기타 검증: `git diff --check` 통과, `uv run python scripts/check_handoff_facts.py` OK, `uv run python scripts/agent_harness_probe.py --strict` OK(14/14), PR quality gate 통과.

## 안전 경계

이번 변경은 등급 2 운영 보정이다.

브로커 API 호출, 실제 주문, 실거래 전환, live 재무장, 자본 배분, 라이브 전략 설정, whitelist/caps, 손실 예산, KIS secret, 감사 로그, 헌법, kernel manifest는 바꾸지 않았다.

`money-path`는 여전히 `PREVIEW_ONLY` / `NO_EDGE_YET`이고, edge-autoarm은 `WAIT_EDGE` / `NO_EDGE`다. 실거래는 기존 엣지 확정과 운영자 승인 경계 없이는 열리지 않는다.

## 다음 세션 판단

현재 최신 autonomous-work selected_work는 `candidate-broad-validation-failure-promotion-recheck-contract`다.

다음 작업은 learning ledger, autonomous-promotion, candidate-result evidence를 함께 읽어 어떤 실패 지문 변화가 억제된 후보 재검토를 허용하는지 결정론적 계약으로 만드는 것이다. 억제 기억은 유지하되, 새 증거가 생겼을 때 되살릴 조건을 닫아야 한다.

같은 패키지를 무작정 재시도하거나 실거래를 여는 작업이 아니다. broad no-edge 축을 별도로 이어갈 때의 다음 후보는 `candidate-broad-no-edge-multi-horizon-signal-experiment`다.
