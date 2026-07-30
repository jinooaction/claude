# HANDOFF-122 — 스펙 120 완료 후보 소비와 관찰 대기

## 한 줄 결론

스펙 120 후보는 released-work 장부에 닫혔고, 자율 작업 루프는 더 이상 완료 후보를 다음 실행 대상으로 다시 보여주지 않고 새 증거 대기 상태를 낸다.

## 기준 상태

- 기준 `main`: `aee5d4302dabec0e9e2f611dfa3bcdd7a3fbbd16` — PR #557 완료 후보 소비 보강
- 기능 커밋: `755110737e52c061271fab6a48a9967a0360f349`
- 직전 기능 머지: `97c1f873dafdf53bb6c6e579c62b7ad64b42ce88` — PR #555 증거 기반 후보 소스 다변화
- 돈 경로: `PREVIEW_ONLY` / `NO_EDGE_YET`
- 실제 주문·취소·실거래 전환·자본 배분: 수행하지 않음

## 무엇을 닫았나

- `specs/120-evidence-based-candidate-source-diversification/spec.md`에 `completed_candidate_id: candidate-evidence-source-diversification-validation-failures`를 추가했다.
- `released_work_probe.py --repo-root .`는 이제 스펙 120 후보를 released로 읽는다.
- `autonomous_work_execution`은 실행 가능 후보, 운영자 승인 필요 후보, 복구 우선 후보가 없고 완료·억제 후보만 남으면 `wait-for-fresh-evidence` / `OBSERVATION_WAIT`를 선택한다.
- 완료 후보를 다시 `selected_work`로 올리던 fallback은 새 증거 대기 패킷으로 대체했다.
- 실행 가능 후보, 운영자 승인 필요 후보, 복구 우선 후보가 있을 때의 기존 선택 순서는 유지했다.

## 검증

- Focused tests: `uv run pytest tests/unit/test_autonomous_work_execution.py tests/unit/test_released_work.py tests/integration/test_autonomous_work_execution_probe.py tests/integration/test_released_work_probe.py -q` → 53 passed.
- 전체 테스트: `uv run pytest` → 2698 passed, 5 skipped.
- 린트: `uv run ruff check src tests` → All checks passed.
- HANDOFF 사실 검증: `uv run python scripts/check_handoff_facts.py` → OK.
- 하네스: `uv run python scripts/agent_harness_probe.py --strict` → OK (14/14).
- 형식 검증: `git diff --check` → clean.
- PR 품질 관문: PR #557 GitHub check `pr-quality-gate` → pass.

## post-merge 자동화

- PR #557 merged at 2026-07-30T22:40:25Z, merge commit `aee5d4302dabec0e9e2f611dfa3bcdd7a3fbbd16`.
- `Deploy on merge to main` run `30587962839`: success.
- `Released work ledger` run `30587962825`: success, commit `aee5d4302dabec0e9e2f611dfa3bcdd7a3fbbd16`, `released_count=39`, 스펙 120 후보 released.
- `Autonomous work execution loop` run `30587962855`: success, commit `aee5d4302dabec0e9e2f611dfa3bcdd7a3fbbd16`, `overall_status=OBSERVATION_WAIT`, selected_work=`wait-for-fresh-evidence`, ranked_count=0.

## 안전 경계

- 위험 등급 2 운영 루프 변경이다.
- 실제 주문, live 재무장, 자본 배분, 라이브 전략 교체, whitelist/caps, 손실 예산은 바꾸지 않았다.
- KIS secret, SSH secret, 감사 로그, 헌법, kernel manifest는 바꾸지 않았다.
- 새 상태는 돈을 움직이라는 신호가 아니라, 새 sidecar 증거가 생길 때까지 기다리라는 신호다.

## 남은 현실

현재 최신 돈 경로는 `PREVIEW_ONLY` / `NO_EDGE_YET`라 실주문은 불가다. 스펙 120 반복 선택 문제는 닫혔고, 다음 작업을 고르려면 다음 scheduled sidecar 갱신 뒤 `released-work`, `autonomous-work`, `money-path`를 다시 읽어 새 `EXECUTION_READY` 후보가 생겼는지 확인한다.
