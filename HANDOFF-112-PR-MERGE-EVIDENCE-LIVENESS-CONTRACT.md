# HANDOFF 112 — PR/머지 증거 생존성 계약 (2026-07-10 KST)

main 코드 베이스라인: `7d06550`(PR #503). 이 작업은 스펙 107이 열어 둔
`candidate-pr-merge-evidence-liveness-contract`를 완료 처리하고, PR 본문 품질 관문,
main merge commit, released-work 장부, deploy 관측이 작업 완료 보고에서 어디까지 살아 있어야
하는지 후보 단위로 고정한 등급 2 운영 체계 보정이다.

## 무엇이 바뀌었나

- `src/auto_invest/analytics/pr_merge_evidence_liveness.py`
  - PR 본문 품질 관문, main merge evidence, released-work completion, deploy-status observation,
    안전 경계를 읽어 `CONTRACT_READY`, `OBSERVATION_WAIT`, `BLOCKED`를 분리한다.
  - `completed_candidate_id: candidate-pr-merge-evidence-liveness-contract`,
    `next_candidate_id: candidate-worktree-concurrency-liveness-contract`를 명시한다.
- `scripts/pr_merge_evidence_liveness_probe.py`
  - `--candidate-id`, `--expected-next-candidate-id`, `--pr-body`, `--main-head`, `--released-work`,
    `--deploy-status`, `--json-out`, `--summary-out`을 받는 읽기 전용 probe를 추가했다.
- `tests/unit/test_pr_merge_evidence_liveness.py`
  - all-pass, deploy 관측 대기, PR 본문 품질 실패, merge evidence 실패, released-work 미완료,
    안전 경계 실패, probe JSON/Markdown 쓰기를 고정했다.
- `tests/integration/test_pr_merge_evidence_liveness_probe.py`
  - CLI가 동일 계약을 파일 입력으로 재현하는지 확인한다.
- `tests/unit/test_autonomous_work_execution.py`
  - 스펙 108 완료 뒤 자율 작업 루프가 `candidate-worktree-concurrency-liveness-contract`로
    전진하는 회귀를 추가했다.
- `specs/108-pr-merge-evidence-liveness-contract/`
  - SDD 산출물과 완료 마커를 남겼다.
- `.specify/feature.json`, `CLAUDE.md`
  - active feature pointer를 스펙 108로 갱신했다.

## 운영상 의미

- 스펙 108 전에는 PR 품질 관문, merge commit, released-work, deploy 관측이 각각은 있었지만,
  "작업 완료" 보고가 어느 증거를 반드시 통과해야 하는지 다음 자율 후보가 직접 읽을 수 없었다.
- 이제 PR/머지 증거는 독립 probe로 확인할 수 있고, 새 세션은 완료 증거 부족을 대기인지 실패인지
  바로 구분할 수 있다.
- 스펙 108이 released-work에 잡히면 다음 자율 후보는
  `candidate-worktree-concurrency-liveness-contract`다.
- 이 변화는 저장소 운영 증거와 다음 작업 후보만 바꾼다. 돈 경로는 계속 `PREVIEW_ONLY`이며
  실주문은 불가하다.

## 배포 후 실제 실행 증거

- PR #503 merge commit: `7d065501eb2dd7d51fbc736e68e19bd1575fd379`
- PR #503 feature commit: `5b71a23d0559cff270516a893a6c61103f31760c`
- 직전 main: `e4035f5`(PR #502, 스펙 107 인계)
- PR #503 post-merge runs:
  - `Deploy on merge to main` run `29076284769`: success
  - `Released work ledger` run `29076284798`: success
  - `Autonomous work execution loop` run `29076284765`: success
- released-work sidecar:
  - `commit=7d065501eb2dd7d51fbc736e68e19bd1575fd379`
  - `overall_status=OK`
  - `candidate-pr-merge-evidence-liveness-contract` released 확인
- autonomous-work sidecar:
  - `overall_status=EXECUTION_READY`
  - selected work `candidate-worktree-concurrency-liveness-contract`
  - title `worktree 동시 작업 생존성 계약`
  - risk grade 2
  - safety impact 없음
  - run id `29076284765`, timestamp `2026-07-10T07:18:44Z`
- deploy status:
  - main commit의 `Deploy on merge to main` workflow run `29076284769`과 deploy job은 success다.
  - 서버 audit_log는 이 컨테이너에서 직접 확인하지 못한다.
  - KIS smoke sidecar 최신 run은 #503 배포의 직접 증거가 아니라 2026-07-10 schedule 실행 증거다.
  - 이 배포는 dry-run worker 코드 반영이며 실거래 전환이 아니다.

## 현재 자율 후보 판정

- `overall_status=EXECUTION_READY`
- `selected_work=candidate-worktree-concurrency-liveness-contract`
- `completed_candidate_id=candidate-pr-merge-evidence-liveness-contract`
- 운영 체계 frontier 상태:
  - `candidate-handoff-truth-liveness-contract` — released
  - `candidate-pr-merge-evidence-liveness-contract` — released
  - `candidate-worktree-concurrency-liveness-contract` — open

## 안전 경계

- 위험 등급: 2(읽기 전용 PR/머지 증거 계약과 후보 전진 보정)
- 실제 주문 실행: 없음
- 브로커 실주문 API 호출: 없음
- 자본 증액, 자본 배분, 허용 종목 확대, 포지션 한도 완화, live 전략 교체, live sentinel 변경: 없음
- 헌법, 커널 목록, 주문 제한, 감사 로그 schema, 비밀값 저장, 외부 유료 서비스 변경: 없음
- 현재 돈 경로는 계속 `PREVIEW_ONLY`다.

## 검증

PR #503 머지 전:

- `uv run pytest tests/unit/test_pr_merge_evidence_liveness.py tests/integration/test_pr_merge_evidence_liveness_probe.py tests/unit/test_autonomous_work_execution.py -q`
  -> 43 passed
- `uv run python scripts/pr_merge_evidence_liveness_probe.py --candidate-id candidate-pr-merge-evidence-liveness-contract --expected-next-candidate-id candidate-worktree-concurrency-liveness-contract ...`
  -> temp all-pass evidence 기준 `CONTRACT_READY`
- `uv run python scripts/released_work_probe.py --repo-root . --json`
  -> `candidate-pr-merge-evidence-liveness-contract` released 확인
- `uv run python scripts/autonomous_work_execution_probe.py --evidence-dir <pipeline-ok> --repo-root . --json`
  -> `candidate-worktree-concurrency-liveness-contract` selected work 확인
- `uv run pytest`
  -> 2569 passed, 4 skipped
- `uv run ruff check src tests`
  -> All checks passed
- `uv run python scripts/agent_harness_probe.py --strict`
  -> OK (14/14)
- `uv run python scripts/check_handoff_facts.py`
  -> OK
- `git diff --check`
  -> 통과
- PR 품질 관문
  -> success
- 머지 직전 `uv run pytest`
  -> 2569 passed, 4 skipped
- 머지 직전 `uv run ruff check src tests`
  -> All checks passed

인계 브랜치에서:

- `uv run pytest -q`
  -> 갱신 전 stale HANDOFF 때문에 하네스 2건 실패, `HANDOFF.md` 수정 후 재실행에서 2569 passed, 4 skipped
- `uv run ruff check src tests`
  -> All checks passed
- `uv run python scripts/check_handoff_facts.py`
  -> OK
- `uv run python scripts/agent_harness_probe.py --strict`
  -> OK (14/14)
- `git diff --check`
  -> 통과

## 다음 세션 한 줄

스펙 108은 PR/머지 증거 생존성 계약을 닫았고, 자율 작업 루프는 이제
`candidate-worktree-concurrency-liveness-contract`를 다음 등급 2 읽기 전용 후보로 제안한다.
