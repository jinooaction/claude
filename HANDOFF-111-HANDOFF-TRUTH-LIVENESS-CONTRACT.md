# HANDOFF 111 — HANDOFF 사실성 생존성 계약 (2026-07-08 KST)

main 코드 베이스라인: `1c412d9`(PR #501). 이 작업은 스펙 106이 열어 둔
`candidate-handoff-truth-liveness-contract`를 완료 처리하고, 다음 세션이 stale HANDOFF와
정상 handoff-only merge baseline을 같은 것으로 오판하지 않도록 읽기 전용 계약을 만든 등급 2
운영 체계 보정이다.

## 무엇이 바뀌었나

- `src/auto_invest/analytics/handoff_truth_liveness.py`
  - 기존 `scripts/check_handoff_facts.py`의 사실성 판정을 자율 후보가 읽을 수 있는
    JSON/Markdown 계약으로 감쌌다.
  - `origin/main` 직접 일치와 handoff-only merge의 첫 부모 기준을 `allowed_baselines`로 노출한다.
  - stale HANDOFF, HANDOFF 파일 결손, 기대 행 불일치를 `BLOCKED`로 분리한다.
  - `completed_candidate_id: candidate-handoff-truth-liveness-contract`,
    `next_candidate_id: candidate-pr-merge-evidence-liveness-contract`를 명시한다.
- `scripts/handoff_truth_liveness_probe.py`
  - `--repo-root`, `--handoff`, `--expect-pytest`, `--expect-ruff`, `--expect-open-pr`,
    `--json-out`, `--summary-out`을 받는 읽기 전용 probe를 추가했다.
- `tests/unit/test_handoff_truth_liveness.py`
  - origin/main 일치, handoff-only 첫 부모 허용, stale HANDOFF 차단, missing HANDOFF 차단,
    기대 행 불일치 차단, probe JSON/Markdown 쓰기를 고정했다.
- `specs/107-handoff-truth-liveness-contract/`
  - SDD 산출물과 완료 마커를 남겼다.
- `.specify/feature.json`, `CLAUDE.md`
  - active feature pointer를 스펙 107로 갱신했다.

## 운영상 의미

- 스펙 107 전에는 `check_handoff_facts.py`가 정상 handoff-only 예외를 알고 있어도, 자율 후보
  단위의 완료 마커와 다음 후보 전진 계약은 없었다.
- 이제 HANDOFF 사실성은 독립 probe로 확인할 수 있고, 새 세션은 `CONTRACT_READY`,
  `handoff_only_first_parent`, `BLOCKED` 같은 상태를 바로 읽을 수 있다.
- 스펙 107이 released-work에 잡히면 다음 자율 후보는
  `candidate-pr-merge-evidence-liveness-contract`다.
- 이 변화는 저장소 사실성 보고와 다음 작업 후보만 바꾼다. 돈 경로는 계속 `PREVIEW_ONLY`이며
  실주문은 불가하다.

## 배포 후 실제 실행 증거

- PR #501 merge commit: `1c412d9c8f592c1d7f168346c97f79bb4efce7dc`
- PR #501 feature commit: `932b85e1666e301ecb58a560302280585a70d663`
- 직전 main: `54f0e09`(PR #500, 스펙 106 인계)
- PR #501 post-merge runs:
  - `Deploy on merge to main` run `28913334443`: success
  - `Released work ledger` run `28913334487`: success
  - `Autonomous work execution loop` run `28913334433`: success
- released-work sidecar:
  - `commit=1c412d9c8f592c1d7f168346c97f79bb4efce7dc`
  - table `released_count=28` entries, unique candidates 27
  - `candidate-handoff-truth-liveness-contract` released 확인
- autonomous-work sidecar:
  - `overall_status=EXECUTION_READY`
  - selected work `candidate-pr-merge-evidence-liveness-contract`
  - title `PR/머지 증거 생존성 계약`
  - risk grade 2
  - safety impact 없음
  - run id `28913334433`, timestamp `2026-07-08T02:35:11Z`
- deploy status:
  - main commit의 `Deploy on merge to main` workflow run `28913334443`과 deploy job은 success다.
  - 서버 audit_log는 이 컨테이너에서 직접 확인하지 못한다.
  - KIS smoke sidecar 최신 run은 #501 배포의 직접 증거가 아니라 2026-07-07 schedule 실행 증거다.
  - 이 배포는 dry-run worker 코드 반영이며 실거래 전환이 아니다.

## 현재 자율 후보 판정

- `overall_status=EXECUTION_READY`
- `selected_work=candidate-pr-merge-evidence-liveness-contract`
- `completed_candidate_id=candidate-handoff-truth-liveness-contract`
- 운영 체계 frontier 상태:
  - `candidate-handoff-truth-liveness-contract` — released
  - `candidate-pr-merge-evidence-liveness-contract` — open
  - `candidate-worktree-concurrency-liveness-contract` — open

## 안전 경계

- 위험 등급: 2(읽기 전용 HANDOFF 사실성 계약과 후보 전진 보정)
- 실제 주문 실행: 없음
- 브로커 실주문 API 호출: 없음
- 자본 증액, 자본 배분, 허용 종목 확대, 포지션 한도 완화, live 전략 교체, live sentinel 변경: 없음
- 헌법, 커널 목록, 주문 제한, 감사 로그 schema, 비밀값 저장, 외부 유료 서비스 변경: 없음
- 현재 돈 경로는 계속 `PREVIEW_ONLY`다.

## 검증

PR #501 머지 전:

- `uv run pytest tests/unit/test_handoff_truth_liveness.py tests/unit/test_autonomous_work_execution.py -q`
  -> 40 passed
- `uv run python scripts/handoff_truth_liveness_probe.py --repo-root . --format json`
  -> current checkout `CONTRACT_READY`, matched baseline `handoff_only_first_parent`
- `uv run python scripts/released_work_probe.py --repo-root . --json`
  -> `candidate-handoff-truth-liveness-contract` released 확인
- `uv run python scripts/autonomous_work_execution_probe.py --evidence-dir <pipeline-ok> --repo-root . --json`
  -> `candidate-pr-merge-evidence-liveness-contract` selected work 확인
- `uv run pytest`
  -> 2560 passed, 4 skipped
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
  -> 2560 passed, 4 skipped
- 머지 직전 `uv run ruff check src tests`
  -> All checks passed

인계 브랜치에서:

- `uv run pytest -q`
  -> 갱신 전 stale HANDOFF 때문에 하네스 2건 실패, `HANDOFF.md` 수정 후 재실행에서 2560 passed, 4 skipped
- `uv run ruff check src tests`
  -> All checks passed
- `uv run python scripts/check_handoff_facts.py`
  -> OK
- `uv run python scripts/agent_harness_probe.py --strict`
  -> OK (14/14)
- `git diff --check`
  -> 통과

## 다음 세션 한 줄

스펙 107은 HANDOFF 사실성 생존성 계약을 닫았고, 자율 작업 루프는 이제
`candidate-pr-merge-evidence-liveness-contract`를 다음 등급 2 읽기 전용 후보로 제안한다.
