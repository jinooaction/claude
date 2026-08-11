# HANDOFF-134 — Validation Failure Command Replay Contract

## 상태

#591이 main에 merge되어 `candidate-broad-validation-failure-command-replay-contract`가 스펙 127로 완료됐다. 이 작업은 돈을 움직이는 패치가 아니라, 검증 실패 child 후보의 명령·안전 재현 범위·실행 증거·다음 진단 action을 읽기 전용 계약으로 고정한 운영 보정이다.

핵심 결론은 이렇다. 막힌 검증 패키지 2개와 명령 4개는 모두 no-live 범위에서 안전하게 읽을 수 있고, released-work가 이번 후보를 소비한 뒤 자율 작업 루프는 다음 child `candidate-broad-validation-failure-data-readiness-contract`로 전진했다.

## 왜 했나

스펙 126은 검증 실패 parent 뒤에 첫 child 후보를 만들었지만, 이 child를 닫지 않으면 다음 세션이 또 실패 명령이 무엇인지, 안전하게 다시 볼 수 있는지, 실행 증거가 있는지부터 다시 확인해야 했다.

안전한 해결은 후보 명령을 무작정 다시 실행하는 것이 아니다. candidate-packages와 candidate-results를 읽어 실패 명령, 종료 코드 증거, 제한된 stdout/stderr 요약, 출력 digest, 다음 action을 기계 판독 가능한 계약으로 남기는 것이다.

## 무엇을 고쳤나

- `specs/127-validation-failure-command-replay/` SDD 산출물을 추가했다.
- `src/auto_invest/analytics/validation_failure_command_replay.py`가 검증 실패 명령 재현 계약을 JSON/Markdown으로 만든다.
- `scripts/validation_failure_command_replay_probe.py`가 sidecar 입력을 받아 계약을 발행한다.
- `candidate_result_executor.py`의 기존 안전 판정을 public helper로 노출해, 새 계약이 같은 안전 기준을 재사용한다.
- 계약은 명령을 실행하지 않는다. 명령 토큰을 기준으로 기존 실행 증거와 조인하고, 비밀값은 가린다.
- `completed_candidate_id: candidate-broad-validation-failure-command-replay-contract` 완료 마커와 완료된 `tasks.md` 덕분에 released-work가 이번 후보를 소비한다.
- `.specify/feature.json`과 `CLAUDE.md`는 최신 완료 스펙 127을 가리킨다.

## 확인한 증거

- PR #591: `https://github.com/jinooaction/claude/pull/591`.
- 기능 커밋: `5bbf0e8`.
- merge commit: `dcf2fc8704fac000ea675cdcbeb693e3a50cdc25`.
- GitHub PR quality gate: runs `31504561350`, `31504627281`, both success.
- released-work run: `31504787462`, commit `dcf2fc8`, released_count 46, 스펙 127 후보 released 포함.
- autonomous-work run: `31504787388`, commit `dcf2fc8`, selected_work `candidate-broad-validation-failure-data-readiness-contract`, status `EXECUTION_READY`, risk_grade 2.
- candidate factory run: `31504787427`, success.
- candidate result executor run: `31504787411`, success. 패키지 2개가 `fail`로 남았고, 각 패키지의 명령 2개씩 실행 증거가 생겼다.
- deploy-on-merge run: `31504787391`, success.
- 로컬 command replay 최신 sidecar 재현: `CONTRACT_READY`, package_count 2, command_count 4, replay_safe_count 4, missing_execution_count 0, unsafe_command_count 0.
- 로컬 전체 검증: `uv run pytest` 2733 passed, 5 skipped.
- 로컬 린트: `uv run ruff check src tests` 통과.
- 기타 검증: `git diff --check` 통과, `uv run python scripts/check_handoff_facts.py` OK, `uv run python scripts/agent_harness_probe.py --strict` OK(14/14), PR quality gate 통과.

## 안전 경계

이번 변경은 등급 2 운영 보정이다.

브로커 API 호출, 실제 주문, 실거래 전환, live 재무장, 자본 배분, 라이브 전략 설정, whitelist/caps, 손실 예산, KIS secret, 감사 로그, 헌법, kernel manifest는 바꾸지 않았다.

`money-path`는 여전히 `PREVIEW_ONLY` / `NO_EDGE_YET`이고, edge-autoarm은 `WAIT_EDGE` / `NO_EDGE`다. 실거래는 기존 엣지 확정과 운영자 승인 경계 없이는 열리지 않는다.

## 다음 세션 판단

현재 최신 autonomous-work selected_work는 `candidate-broad-validation-failure-data-readiness-contract`다.

다음 작업은 candidate history support, portfolio TOML, public-data, regime-stratify 증거를 함께 읽어 history root, 관측 기간, 데이터 결측 원인을 검증 패키지별 PASS/WAIT/FAIL로 분리하는 것이다. 같은 패키지를 무작정 재시도하거나 실거래를 여는 작업이 아니다.

그 다음 child 후보는 `candidate-broad-validation-failure-package-kind-expansion-contract`이고, 이어서 `candidate-broad-validation-failure-promotion-recheck-contract`가 남아 있다.
