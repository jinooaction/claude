# HANDOFF-135 — Validation Failure Data Readiness Contract

## 상태

#593이 main에 merge되어 `candidate-broad-validation-failure-data-readiness-contract`가 스펙 128로 완료됐다. 이 작업은 돈을 움직이는 패치가 아니라, 검증 실패 child 후보의 데이터 준비 여부를 읽기 전용 계약으로 고정한 운영 보정이다.

핵심 결론은 이렇다. 검증 실패 패키지 2개는 데이터 결측 때문에 실패한 것이 아니다. candidate history support, portfolio TOML, history root, 실행 metric, public-data, regime-stratify 증거를 함께 보면 패키지 2개와 포트폴리오 데이터 표면 3개가 모두 `PASS_DATA_READY`다. released-work가 이번 후보를 소비한 뒤 자율 작업 루프는 다음 child `candidate-broad-validation-failure-package-kind-expansion-contract`로 전진했다.

## 왜 했나

스펙 127은 실패 명령과 실행 증거를 고정했다. 하지만 그 다음에는 "데이터가 없어서 실패했나?"와 "데이터는 있는데 전략 엣지가 약했나?"를 분리해야 했다.

안전한 해결은 같은 검증 명령을 막연히 다시 실행하는 것이 아니다. candidate-packages, candidate-results, candidate history support, portfolio TOML, public-data, regime-stratify를 읽어 패키지별 데이터 준비도를 `PASS_DATA_READY`, `WAITING_FOR_EVIDENCE`, `BLOCKED_DATA_INPUT`으로 남기는 것이다.

## 무엇을 고쳤나

- `specs/128-validation-failure-data-readiness/` SDD 산출물을 추가했다.
- `src/auto_invest/analytics/validation_failure_data_readiness.py`가 검증 실패 데이터 준비도 계약을 JSON/Markdown으로 만든다.
- `scripts/validation_failure_data_readiness_probe.py`가 sidecar 입력을 받아 계약을 발행한다.
- `tests/unit/test_validation_failure_data_readiness.py`가 현재 두 패키지와 세 포트폴리오 데이터 표면의 준비 상태를 고정한다.
- `autonomous_work_execution.py`가 candidate-packages의 nested `promotion_patch.factory_diagnostics`, `factory_next_actions`, `factory_retryable`을 broad validation failure 참조로 읽는다. 실제 sidecar처럼 candidate-results가 `fail`이고 retryable 정보가 candidate-packages 아래에만 남아도 child 순서가 끊기지 않는다.
- `completed_candidate_id: candidate-broad-validation-failure-data-readiness-contract` 완료 마커와 완료된 `tasks.md` 덕분에 released-work가 이번 후보를 소비한다.
- `.specify/feature.json`과 `CLAUDE.md`는 최신 완료 스펙 128을 가리킨다.

## 확인한 증거

- PR #593: `https://github.com/jinooaction/claude/pull/593`.
- 기능 커밋: `e27d58b`.
- merge commit: `d7e473db729650d0faa3f18dbe1887000a6a5045`.
- GitHub PR quality gate: run `31554170938`, success.
- released-work run: `31554206845`, commit `d7e473d`, released_count 47, 스펙 128 후보 released 포함.
- autonomous-work run: `31554206817`, commit `d7e473d`, selected_work `candidate-broad-validation-failure-package-kind-expansion-contract`, status `EXECUTION_READY`, risk_grade 2, package_kind package_count 2, retryable_count 2.
- deploy-on-merge run: `31554206841`, success. 컨테이너에서 Actions run과 job success는 확인했지만 서버 audit_log는 운영자 또는 서버 접근 표면에서만 확인할 수 있다.
- 최신 data readiness sidecar 재현: `CONTRACT_READY`, package_count 2, surface_count 3, data_ready_count 2, waiting_count 0, blocked_count 0, execution_evidence_count 3.
- local released-work/autonomous-work 재현: released_count 47, selected_work `candidate-broad-validation-failure-package-kind-expansion-contract`.
- 로컬 전체 검증: `uv run pytest` 2739 passed, 5 skipped.
- 로컬 린트: `uv run ruff check src tests` 통과.
- 기타 검증: `git diff --check` 통과, `uv run python scripts/check_handoff_facts.py` OK, `uv run python scripts/agent_harness_probe.py --strict` OK(14/14), PR quality gate 통과.

## 안전 경계

이번 변경은 등급 2 운영 보정이다.

브로커 API 호출, 실제 주문, 실거래 전환, live 재무장, 자본 배분, 라이브 전략 설정, whitelist/caps, 손실 예산, KIS secret, 감사 로그, 헌법, kernel manifest는 바꾸지 않았다.

`money-path`는 여전히 `PREVIEW_ONLY` / `NO_EDGE_YET`이고, edge-autoarm은 `WAIT_EDGE` / `NO_EDGE`다. 실거래는 기존 엣지 확정과 운영자 승인 경계 없이는 열리지 않는다.

## 다음 세션 판단

현재 최신 autonomous-work selected_work는 `candidate-broad-validation-failure-package-kind-expansion-contract`다.

다음 작업은 strategy_backtest와 portfolio_backtest 실패를 나눠 전략군, 포트폴리오 구성, 보유 기간, 산출 증거별 no-live 후보 축을 재정렬하는 것이다. 데이터 입력 문제를 다시 의심하는 것보다, 데이터 준비 완료 상태에서 실패 구조를 넓게 나누는 것이 다음 순서다.

그 다음 child 후보는 `candidate-broad-validation-failure-promotion-recheck-contract`가 남아 있다.
