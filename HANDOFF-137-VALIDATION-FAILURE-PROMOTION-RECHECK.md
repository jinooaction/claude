# HANDOFF-137 — Validation Failure Promotion Recheck Contract

## 상태

#597이 main에 merge되어 `candidate-broad-validation-failure-promotion-recheck-contract`가 스펙 130으로 완료됐다. 이 작업은 돈을 움직이는 패치가 아니라, 억제된 검증 실패 후보를 언제 다시 열 수 있는지 정하는 no-live 운영 계약이다.

핵심 결론은 이렇다. 현재 `candidate-1ed634d8bf6d`와 `candidate-cc96b35062da`는 같은 실패 지문이라 계속 억제한다. 다만 candidate-result가 fail/blocked에서 벗어나거나, promotion stage가 DISCARD에서 벗어나거나, 최신 learning ledger가 명시적 재검토 조건을 주거나, 실패 fingerprint가 바뀌면 재검토를 허용할 수 있게 됐다. 이 child가 released-work에 소비되면서 자율 작업 루프는 검증 실패 묶음을 끝내고 다음 broad no-edge 후보로 전진했다.

## 왜 했나

learning ledger의 폐기 기억은 필요하다. 같은 실패 후보를 계속 되살리면 자동 루프가 같은 곳에서 돈과 시간을 잃는다. 하지만 재검토 조건이 전혀 없으면, 검증 결과가 나중에 좋아져도 후보가 닫힌 채 남을 수 있다.

안전한 해결은 후보를 바로 재실행하거나 실거래 기준을 낮추는 것이 아니다. ledger, promotion, result evidence를 함께 읽어 "현재는 왜 닫혀 있는가"와 "무엇이 바뀌면 다시 열 수 있는가"를 기계 판독 가능한 계약으로 남기는 것이다.

## 무엇을 고쳤나

- `specs/130-validation-failure-promotion-recheck/` SDD 산출물을 추가했다.
- `src/auto_invest/analytics/validation_failure_promotion_recheck.py`가 후보별 승격 재검토 계약을 JSON/Markdown으로 만든다.
- `scripts/validation_failure_promotion_recheck_probe.py`가 sidecar 입력을 받아 계약을 발행한다.
- `tests/unit/test_validation_failure_promotion_recheck.py`가 현재 후보 억제 유지, result pass 시 재검토 허용, 증거 누락 대기, 안전 경계를 고정한다.
- `tests/unit/test_autonomous_work_execution.py`가 promotion-recheck 후보 released 뒤 같은 child를 반복 선택하지 않는 회귀를 고정한다.
- `completed_candidate_id: candidate-broad-validation-failure-promotion-recheck-contract` 완료 마커와 완료된 `tasks.md` 덕분에 released-work가 이번 후보를 소비한다.
- `.specify/feature.json`과 `CLAUDE.md`는 최신 완료 스펙 130을 가리킨다.

## 확인한 증거

- PR #597: `https://github.com/jinooaction/claude/pull/597`.
- 기능 커밋: `8de3136`.
- merge commit: `cc7f0508d033133f074181760553786e45bd89ea`.
- GitHub PR quality gate: runs `31574227196`, `31574263368`, `31574271779`, all success.
- deploy-on-merge run: `31574288074`, commit `cc7f050`, success. 컨테이너에서 Actions run success는 확인했지만 서버 audit_log는 운영자 또는 서버 접근 표면에서만 확인할 수 있다.
- released-work run: `31574288078`, commit `cc7f050`, released_count 49, 스펙 130 후보 released 포함.
- autonomous-work run: `31574288096`, commit `cc7f050`, selected_work `candidate-broad-no-edge-multi-horizon-signal-experiment`, status `EXECUTION_READY`, risk_grade 2.
- 최신 promotion-recheck sidecar 재현: `CONTRACT_READY`, candidate_count 2, suppressed_count 2, allowed_recheck_count 0, waiting_count 0.
- local released-work/autonomous-work 재현: promotion-recheck child released, broad validation failure frontier map 4개 모두 released, 다음 selected_work는 `candidate-broad-no-edge-multi-horizon-signal-experiment`.
- 로컬 전체 검증: `uv run pytest` 2750 passed, 5 skipped.
- 로컬 린트: `uv run ruff check src tests` 통과.
- 기타 검증: `git diff --check` 통과, `uv run python scripts/check_handoff_facts.py` OK, `uv run python scripts/agent_harness_probe.py --strict` OK(14/14), PR quality gate 통과.

## 안전 경계

이번 변경은 등급 2 운영 보정이다.

브로커 API 호출, 실제 주문, 실거래 전환, live 재무장, 자본 배분, 라이브 전략 설정, whitelist/caps, 손실 예산, KIS secret, 감사 로그, 헌법, kernel manifest는 바꾸지 않았다.

`money-path`는 여전히 `PREVIEW_ONLY` / `NO_EDGE_YET`이고, edge-autoarm은 `WAIT_EDGE` / `NO_EDGE`다. 실거래는 기존 엣지 확정과 운영자 승인 경계 없이는 열리지 않는다.

## 다음 세션 판단

현재 최신 autonomous-work selected_work는 `candidate-broad-no-edge-multi-horizon-signal-experiment`다.

검증 실패 child 후보는 command replay, data readiness, package-kind expansion, promotion recheck 네 개가 모두 released로 닫혔다. 다음 작업은 broad no-edge 축에서 다중 보유 기간과 신호군을 넓히는 no-live 실험 설계다.

주문 제출, live 재무장, 자본 배분은 하지 않는다. 현재 돈 경로는 여전히 `PREVIEW_ONLY`/`NO_EDGE_YET`이다.
