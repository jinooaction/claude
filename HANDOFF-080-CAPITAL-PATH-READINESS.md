# HANDOFF 080 — 자본 경로 준비도 루프 (2026-07-01 KST)

main 코드 베이스라인: `23ec54b`(PR #430). 스펙 076은 money-path, edge-autoarm,
reassign, 전진 페이퍼, KIS smoke, promotion/evolution sidecar를 읽어 자본 투입 준비도와
다음 안전 행동을 자동 산출하는 읽기 전용 루프다.

## 무엇이 바뀌었나

- `src/auto_invest/analytics/capital_path_readiness.py`
  - `readiness_state`, `live_money_status`, `capital_ladder_stage`, `blocking_gate`,
    `next_action_ko`, 우선 후보, 억제 후보, 입력 증거 표면을 산출한다.
  - money-path의 실제 돈 상태와 자본 사다리 단계를 우선 근거로 삼는다.
  - evolution backlog의 `live_readiness` 등 자본 경로 관련 후보를 우선 후보로 올린다.
  - learning ledger와 promotion summary가 실패로 표시한 후보는 억제 후보로 남긴다.
  - money-path가 없거나 깨지면 `UNKNOWN`으로 fail-closed 처리한다.
- `scripts/capital_path_readiness_probe.py`
  - `--manifest`로 소비 sidecar 목록을 한 곳에서 제공한다.
  - workflow와 로컬 smoke가 같은 코어를 호출해 JSON/Markdown 보고서를 만든다.
- `.github/workflows/capital-path-readiness.yml`
  - 매일 08:10 UTC와 main push 때 실행된다.
  - automation sidecar 브랜치를 읽고 `automation/capital-path-readiness-last-run`만 발행한다.
- `src/auto_invest/analytics/pipeline_liveness.py`
  - `capital-path-readiness`를 비핵심 보고 sidecar로 감시 대상에 등록했다.
- `specs/076-capital-path-readiness-loop/`
  - 스펙, 계획, 작업 목록, 데이터 모델, 계약, quickstart를 남겼다.

## 운영상 의미

- 운영자는 더 이상 money-path, reassign, promotion/evolution sidecar를 따로 읽어
  "지금 돈 경로가 어디까지 왔나"를 손으로 조합하지 않아도 된다.
- 현재 최신 sidecar 기준 자본 경로는 `ACCUMULATING_EDGE / PREVIEW_ONLY`다.
  이것은 "실제 주문 가능"이 아니라 "전진 관측과 기존 자본 사다리 게이트를 계속 누적"이라는 뜻이다.
- 최신 blocker는 `전진 관측 부족: 14/20`이다.
- 우선 후보 1순위는 `candidate-fd04772a23c5`(`live_readiness`, 점수 597)다.
- `candidate-1ed634d8bf6d`, `candidate-cc96b35062da`는 learning ledger 기준 rejected 후보로 억제된다.

## 배포 후 실제 실행 증거

- PR #430 merge commit: `23ec54be9a7c98b6b0c10cb038f5c25249713fa1`
- `Deploy on merge to main` run `28518083151`: success, commit `23ec54b`
- `Capital path readiness` run `28518083087`: success, commit `23ec54b`
- 최신 `origin/automation/capital-path-readiness-last-run:LAST_RUN.md`
  - run `28518083087`, trigger `push`, timestamp `2026-07-01T12:38:37Z`
  - `readiness_state=ACCUMULATING_EDGE`
  - `live_money_status=PREVIEW_ONLY`
  - `capital_ladder_stage=ACCUMULATING_EDGE`
  - `blocking_gate=전진 관측 부족: 14/20`
  - rejected 후보 2개 억제 확인
- `Pipeline liveness`는 main push 직후 병렬 실행에서 새 sidecar보다 먼저 돌아 처음엔
  `capital-path-readiness=MISSING`으로 `DEGRADED`를 기록했다. 같은 main commit으로
  workflow dispatch run `28518134667`을 재실행했고 최신 liveness sidecar는 `overall=OK`,
  `capital-path-readiness=OK`다.
- `Candidate result executor` run `28518083233`도 success로 완료됐다.
- 최신 KIS smoke sidecar는 run `28500268994`, commit `f9f8908`, `smoke_state=success`,
  `key_valid=true`다. #430과 같은 commit의 직접 KIS smoke는 아니며, 브로커 연결 생존의 참고 증거다.

## 안전 경계

- 위험 등급: 2(운영 자동화 추가)
- 실제 주문 실행: 없음
- 브로커 실주문 API 호출: 없음
- 자본 증액, 허용 종목 확대, 포지션 한도 완화, live 전략 교체, live sentinel 변경: 없음
- 헌법, 커널 목록, 주문 제한, 비밀값, 감사 로그 변경: 없음
- 기존 `money-path`, `edge-autoarm`, `reassign`, K1 한도, K2 허용 종목, live gate를
  자본 투입 판단의 원천으로 유지한다.
- 배포 성공은 dry-run worker 코드 반영이다. 실거래 전환이나 실제 주문을 의미하지 않는다.

## 검증

PR #430 머지 전:

- `uv run pytest tests/unit/test_capital_path_readiness.py tests/integration/test_capital_path_readiness_probe.py`
  -> 8 passed
- `uv run ruff check src/auto_invest/analytics/capital_path_readiness.py scripts/capital_path_readiness_probe.py tests/unit/test_capital_path_readiness.py tests/integration/test_capital_path_readiness_probe.py`
  -> All checks passed
- 최신 sidecar local smoke -> `ACCUMULATING_EDGE / PREVIEW_ONLY / ACCUMULATING_EDGE`,
  우선 후보 점수 확인, rejected 후보 2개 억제 확인
- `uv run pytest` -> 2374 passed, 4 skipped
- `uv run ruff check src tests` -> All checks passed
- `git diff --check` -> OK
- `uv run python scripts/check_pr_quality_gate.py .verify/pr-body-076.md` -> OK
- `uv run python scripts/check_handoff_facts.py` -> OK
- `uv run python scripts/agent_harness_probe.py --strict` -> OK (14/14)
- PR 품질 관문 -> success, mergeable clean, merge 방식으로 main에 병합
- 머지 직전 전체 테스트와 린트를 다시 실행해 같은 결과를 확인했다.

머지 후:

- deploy run `28518083151`: success
- capital path readiness run `28518083087`: success
- latest capital path sidecar verification -> `readiness_state=ACCUMULATING_EDGE`,
  `live_money_status=PREVIEW_ONLY`, `blocking_gate=전진 관측 부족: 14/20`
- pipeline liveness 재실행 run `28518134667`: success, latest sidecar `overall=OK`

## 다음 세션 한 줄

스펙 076은 돈 경로 상태를 새 sidecar 하나로 묶었지만, 현재 상태는 여전히
`ACCUMULATING_EDGE / PREVIEW_ONLY`다. 다음 작업은 실주문 우회가 아니라
우선 후보 `candidate-fd04772a23c5`처럼 기존 게이트와 증거를 더 강하게 정렬하는 것이다.
