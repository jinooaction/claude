# HANDOFF 081 — 자율 작업 실행 루프 (2026-07-01 KST)

main 코드 베이스라인: `996ce56`(PR #432). 스펙 077은 기존 자율 성장·승격·후보 검증·자본 준비도·파이프라인 생존 sidecar를 읽어, 다음 Codex 작업 패킷을 `automation/autonomous-work-execution-last-run`에 자동 발행하는 읽기 전용 운영 루프다.

## 무엇이 바뀌었나

- `src/auto_invest/analytics/autonomous_work_execution.py`
  - 입력 sidecar를 `EvidenceSurface`로 정규화한다.
  - 자본 경로 우선 후보, evolution backlog, promotion summary, candidate factory/result evidence를 `WorkPacket`으로 변환한다.
  - pipeline liveness가 `CRITICAL`이면 일반 성장 후보보다 자동화 복구 작업을 우선한다.
  - risk grade와 safety surface를 보고 위험 후보를 `OPERATOR_APPROVAL_REQUIRED`로 분리한다.
  - learning ledger의 rejected 후보는 다른 sidecar에서 다시 올라와도 `SUPPRESSED`로 억제한다.
- `scripts/autonomous_work_execution_probe.py`
  - `--manifest`로 소비 sidecar 목록을 제공한다.
  - workflow와 로컬 smoke가 같은 코어를 호출해 JSON/Markdown 보고서를 만든다.
- `.github/workflows/autonomous-work-execution.yml`
  - 매일 09:10 UTC와 main push 때 실행된다.
  - automation sidecar 브랜치를 읽고 `automation/autonomous-work-execution-last-run`만 발행한다.
- `src/auto_invest/analytics/pipeline_liveness.py`
  - `autonomous-work-execution`을 비핵심 보고 sidecar로 감시 대상에 등록했다.
- `specs/077-autonomous-work-execution-loop/`
  - 스펙, 계획, 작업 목록, 데이터 모델, 계약, quickstart를 남겼다.

## 운영상 의미

- 운영자가 매번 "다음엔 뭘 해야 하냐"고 묻지 않아도, 최신 sidecar 하나가 다음 작업 후보를 보여준다.
- 현재 최신 작업 패킷은 `candidate-fd04772a23c5`다.
  - 제목: `돈 경로 준비도와 기존 게이트 정렬`
  - 상태: `EXECUTION_READY`
  - 위험 등급: 2
  - 점수: 3597
- `candidate-1ed634d8bf6d`, `candidate-cc96b35062da`는 learning ledger rejected 기록 때문에 `SUPPRESSED`다.
- 이것은 자동 코드 작성자가 아니다. 실제 구현, 테스트, PR, 머지는 기존 Codex 작업 절차와 품질 관문을 통과해야 한다.

## 배포 후 실제 실행 증거

- PR #432 merge commit: `996ce56380b6e26d7ded84b7d552cdd06fbf6436`
- `Deploy on merge to main` run `28523867765`: success, commit `996ce56`
- `Autonomous work execution loop` run `28523867803`: success, commit `996ce56`
- 최신 `origin/automation/autonomous-work-execution-last-run:LAST_RUN.md`
  - run `28523867803`, trigger `push`, timestamp `2026-07-01T14:11:28Z`
  - `overall_status=EXECUTION_READY`
  - `selected_work=candidate-fd04772a23c5`
  - `risk_grade=2`, `priority_score=3597`
  - 입력 증거 8개 모두 `present=true`, `parse_status=ok`
- `Pipeline liveness`는 main push 직후 병렬 실행에서 새 sidecar보다 먼저 돌아 처음엔
  `autonomous-work-execution=PENDING`으로 기록했다. 같은 main commit으로 workflow dispatch run
  `28523925493`을 재실행했고 최신 liveness sidecar는 `overall=OK`,
  `autonomous-work-execution=OK`다.
- `KIS smoke` workflow dispatch run `28523981341`: success, commit `996ce56`,
  `secrets_present=true`, `key_valid=true`, `smoke_state=success`, `smoke_exit=0`.

## 안전 경계

- 위험 등급: 2(운영 자동화 추가)
- 실제 주문 실행: 없음
- 브로커 실주문 API 호출: 없음
- 자본 증액, 허용 종목 확대, 포지션 한도 완화, live 전략 교체, live sentinel 변경: 없음
- 헌법, 커널 목록, 주문 제한, 비밀값, 감사 로그 변경: 없음
- workflow 안전 계약 테스트가 `KIS_`, `ssh `, live rebalance, 주문 제출, PR 생성, main 직접 push 문자열 부재를 확인한다.
- 배포 성공은 dry-run worker 코드 반영이다. 실거래 전환이나 실제 주문을 의미하지 않는다.

## 검증

PR #432 머지 전:

- `uv run pytest tests/unit/test_autonomous_work_execution.py tests/integration/test_autonomous_work_execution_probe.py tests/integration/test_pipeline_liveness_probe.py`
  -> 14 passed
- `uv run ruff check src/auto_invest/analytics/autonomous_work_execution.py scripts/autonomous_work_execution_probe.py tests/unit/test_autonomous_work_execution.py tests/integration/test_autonomous_work_execution_probe.py src/auto_invest/analytics/pipeline_liveness.py`
  -> All checks passed
- 최신 sidecar local smoke -> `selected_work=candidate-fd04772a23c5`,
  `overall_status=EXECUTION_READY`, ledger rejected 후보 2개 `SUPPRESSED`
- `uv run pytest` -> 2384 passed, 4 skipped
- `uv run ruff check src tests` -> All checks passed
- `git diff --check` -> OK
- `uv run python scripts/check_pr_quality_gate.py /tmp/pr-077-autonomous-work-execution.md` -> OK
- `uv run python scripts/check_handoff_facts.py` -> OK
- `uv run python scripts/agent_harness_probe.py --strict` -> OK (14/14)
- PR 품질 관문 -> success, mergeable clean, merge 방식으로 main에 병합
- 머지 직전 전체 테스트와 린트를 다시 실행해 같은 결과를 확인했다.

머지 후:

- deploy run `28523867765`: success
- autonomous work execution run `28523867803`: success
- latest autonomous work sidecar verification -> `EXECUTION_READY`,
  `selected_work=candidate-fd04772a23c5`, rejected 후보 2개 억제 확인
- pipeline liveness 재실행 run `28523925493`: success, latest sidecar `overall=OK`,
  `autonomous-work-execution=OK`
- KIS smoke run `28523981341`: success, commit `996ce56`, `key_valid=true`

handoff 갱신 전 main 검증:

- `uv run ruff check src tests` -> All checks passed
- `uv run pytest -q` -> 2382 passed, 4 skipped, 2 failed
- 실패 2건은 `HANDOFF.md`가 아직 `23ec54b`를 가리켜 strict harness가 `DEGRADED`가 된 예상 실패다. 이 handoff 갱신이 그 원인을 바로잡는다.

## 다음 세션 한 줄

스펙 077은 "다음 작업을 묻지 않아도 되는 루프"를 main에 넣었다. 최신 자동 작업 패킷은
`candidate-fd04772a23c5`이며, 다음 구현 세션은 이 후보를 스펙/구현 작업으로 이어가면 된다.
