# HANDOFF-117 — 스펙 118 운영자 이해 가능 보고 생존성 계약

## 한 줄 결론

스펙 118은 Codex의 최종 완료 보고가 운영자가 다시 묻지 않아도 되는 수준으로 결론, 변경 내용, 돈 경로와 안전 경계 의미, 검증, 남은 위험을 담는지 읽기 전용으로 판정하는 계약을 main에 넣었다.

## 기준 상태

- 기준 `main`: `158052add91cc059b4d61a18ea1e5efad508185b` — PR #525 스펙 118 머지
- 기능 커밋: `34831f840af30d4b65934f70ca3108cd0b846b40`
- PR 생성 체크 커밋: `9f56c0f7174b32c0d9f936c01a7db0169c349923`
- 확인 시점: 2026-07-15 KST
- 돈 경로: 계속 `PREVIEW_ONLY`
- 실제 주문·취소·실거래 전환: 수행하지 않음
- live sentinel, capital, whitelist, caps, loss budget, 헌법, kernel manifest, 비밀값: 변경 없음

## 해결한 실패 모드

이 저장소는 이미 `AGENTS.md`, `.codex/quality-gate.md`, PR 템플릿, 첫 판단 품질 과제로 "운영자가 이해 가능한 완료 보고"를 요구한다. 그러나 최종 보고가 다음 항목을 실제로 담는지 후보 단위로 확인하는 계약은 없었다.

1. 첫 문장 결론이 실제 운영 상태 변화를 말하는가.
2. 무엇을 만들었거나 고쳤는가.
3. 돈 경로, 자동화, 안전 경계, 다음 세션 행동에 어떤 의미가 있는가.
4. 무엇으로 확인했는가.
5. 아직 남은 위험이나 다음 관찰 지점은 무엇인가.
6. PR 번호, 커밋, 테스트 개수 같은 증거만 나열하고 의미 설명을 빠뜨리지 않는가.

스펙 118은 이 항목을 `src/auto_invest/analytics/operator_report_liveness.py`와 `scripts/operator_report_liveness_probe.py`로 분리했다. 보고 텍스트가 공급되면 보고 범주별로 `PASS`, `WAIT`, `FAIL`을 계산하고, 규칙 표면과 released-work 증거까지 합쳐 전체 상태를 `CONTRACT_READY`, `OBSERVATION_WAIT`, `BLOCKED`로 낸다.

## 적용 기준

- `AGENTS.md`가 최종 보고 필수 항목을 계속 담고 있어야 한다.
- `.codex/quality-gate.md`가 운영자 이해 가능 보고 관문을 계속 담고 있어야 한다.
- `.github/pull_request_template.md`가 위험 등급, 문제 정의, 검증, 하네스, 안전 경계, 인계를 계속 요구해야 한다.
- `.codex/harness/quality_tasks.toml`의 `QUALITY-006`이 `honest_reporting`, `operator_readability`, `problem_definition`, `safety_boundary`, `handoff_awareness` 범주를 계속 덮어야 한다.
- `HANDOFF.md`가 `git_ground_truth`, `/sync`, `AGENTS.md`, 운영자 응대 핵심 규칙을 계속 가리켜야 한다.
- released-work가 `candidate-operator-report-liveness-contract`를 읽으면 이 후보는 다시 자율 후보로 선택되면 안 된다.

## 실패 시 동작

- 규칙 표면이 사라지면 `BLOCKED`다.
- 최종 보고 텍스트가 없으면 `OBSERVATION_WAIT`다.
- 최종 보고가 증거만 나열하고 의미·검증·남은 위험을 빠뜨리면 `WAIT` 또는 `FAIL`이다.
- released-work가 아직 후보를 소비하지 않았으면 `OBSERVATION_WAIT`다.
- 안전 불변식은 새 모듈이 주문, 자본, live 전략, whitelist/caps, 비밀값, 외부 유료 서비스, 네트워크 호출을 하지 않는다는 점을 명시한다.

## 검증

- 구현 전 focused regression: `uv run pytest tests/unit/test_operator_report_liveness.py tests/integration/test_operator_report_liveness_probe.py tests/unit/test_autonomous_work_execution.py -q` → `ModuleNotFoundError`로 실패. 기존 모듈이 없음을 확인했다.
- 구현 후 focused regression: 같은 명령 → 45 passed.
- 전체 테스트: PR #525 머지 전 `uv run pytest -q` → 2638 passed, 4 skipped.
- 린트: `uv run ruff check src tests` → All checks passed.
- diff 공백: `git diff --check` → 통과.
- 하네스: `uv run python scripts/agent_harness_probe.py --strict` → OK (14/14).
- HANDOFF 사실 검증: `uv run python scripts/check_handoff_facts.py` → OK.
- PR 품질 관문: PR #525 본문을 저장한 임시 파일로 `uv run python scripts/check_pr_quality_gate.py` 실행 → `pr-quality-gate-ok`.

## post-merge 자동화

#525 main push 뒤 다음 GitHub Actions run이 success다.

- `Deploy on merge to main`: `29414899987`
- `Released work ledger`: `29414899929`
- `Autonomous work execution loop`: `29414899957`

KIS smoke는 broker 또는 live smoke 경로가 바뀔 때만 push에서 실행된다. 이번 변경은 운영 보고 계약이라 새 KIS smoke push 실행은 없었다. 최신 KIS smoke sidecar는 schedule run `29391711482`, `commit=7be7bde`, `smoke_state=success`, `key_valid=true`다.

#525 직후 released-work sidecar는 `specs/118-operator-report-liveness-contract/tasks.md`의 T024/T025가 아직 닫히기 전이라 스펙 118을 제외했다. 이 handoff 갱신은 T024/T025 완료 상태를 남기므로 다음 released-work run이 `candidate-operator-report-liveness-contract`를 released로 소비해야 한다.

## 남은 운영 확인

- 최종 보고 텍스트는 워크플로 또는 수동 파일로 제공되어야 한다. 채팅 내용을 자동 수집하지 않는다.
- 판정은 최소 의미 범주 계약이다. 모든 문장 품질이나 운영자 만족도를 완전히 보장하지 않는다.
- 스펙 118의 `next_candidate_id`는 `none`이다. 다음 일반 후보는 후속 frontier 갱신 전까지 비어 있다.
- 실제 서버 audit_log, 운영자 GitHub Actions Summary, KIS 계좌의 열린 주문과 보유 상태는 이 저장소 작업만으로 확인하지 않았다.

## 다음 후보

스펙 118 기준 다음 후보는 `none`이다. 다음 작업을 고르려면 후속 autonomous-work sidecar 또는 frontier 지도 갱신을 먼저 확인한다.
