# HANDOFF 094 — source diversification 산출 후보 완료 폐쇄 (2026-07-03 KST)

main 코드 베이스라인: `2f64cba`(PR #467). 이 작업은 스펙 089가 만든
`candidate-source-diversification-sidecar-bottleneck` 산출 후보를 released-work 장부로 닫고 다음
거시 후보로 전진시킨 등급 2 운영 자동화 보정이다.

## 무엇이 바뀌었나

- `specs/090-source-diversification-candidate-closure/`
  - completed marker `candidate-source-diversification-sidecar-bottleneck`을 남겼다.
  - released-work가 모든 tasks 완료 후 이 후보를 released 후보로 기록하게 했다.
  - quickstart는 released-work 재현과 최신 sidecar replay 절차를 남긴다.
- `.specify/feature.json`, `CLAUDE.md`
  - 최신 스펙 포인터를 스펙 090으로 갱신했다.
- `tests/unit/test_autonomous_work_execution.py`
  - released source-diversification 산출 후보가 다시 `EXECUTION_READY`가 되지 않고
    `candidate-autonomous-growth-objective-calibration`으로 전진하는 회귀 테스트를 추가했다.

## 운영상 의미

- 스펙 089가 만든 산출 후보를 다음 세션이 다시 새 작업으로 착수하지 않는다.
- 최신 released-work sidecar는 `candidate-source-diversification-sidecar-bottleneck`을 released 처리한다.
- 최신 autonomous-work sidecar는 다음 후보를 `candidate-autonomous-growth-objective-calibration`으로 고른다.
- 이 변경은 완료 후보 장부와 다음 작업 선택만 바꾼다. 돈 경로는 계속 `PREVIEW_ONLY`다.

## 배포 후 실제 실행 증거

- PR #467 merge commit: `2f64cbadc0e5ebe36fa84e26b9d839ac439caef5`
- PR #467 feature commit: `a167fee`
- PR #467 post-merge runs:
  - `Deploy on merge to main` run `28643121916`: success
  - `Released work ledger` run `28643121934`: success
  - `Autonomous work execution loop` run `28643121911`: success
- 최신 released-work sidecar:
  - commit `2f64cba`
  - `candidate-source-diversification-sidecar-bottleneck` status `released`
  - spec `090-source-diversification-candidate-closure`
- 최신 autonomous-work sidecar:
  - commit `2f64cba`
  - selected `candidate-autonomous-growth-objective-calibration`
  - status `EXECUTION_READY`
  - risk_grade 2
  - safety_impact 없음
- deploy status:
  - deploy job success
  - 서버 audit_log와 GitHub Actions Summary 원문은 이 컨테이너에서 직접 확인하지 못한다.
  - KIS smoke 최신 sidecar는 success지만 commit `55ec2da` 기준 스케줄 run이라 #467 직접 증거는 아니다.

## 안전 경계

- 위험 등급: 2(운영 자동화 완료 후보 폐쇄)
- 실제 주문 실행: 없음
- 브로커 실주문 API 호출: 없음
- 자본 증액, 자본 배분, 허용 종목 확대, 포지션 한도 완화, live 전략 교체, live sentinel 변경: 없음
- 헌법, 커널 목록, 주문 제한, 감사 로그 schema, 비밀값 저장, 외부 유료 서비스 변경: 없음
- 현재 돈 경로는 계속 `PREVIEW_ONLY`다.

## 검증

PR #467 머지 전:

- `uv run pytest tests/unit/test_autonomous_work_execution.py -q`
  -> 12 passed
- `uv run python scripts/released_work_probe.py --repo-root . --run-id local-090 --commit "$(git rev-parse HEAD)" --json-out /tmp/released_work_090.json --summary-out /tmp/released_work_090.md`
  -> `candidate-source-diversification-sidecar-bottleneck` released
- 최신 sidecar replay with repo-root override
  -> selected `candidate-autonomous-growth-objective-calibration`
- `uv run pytest -q`
  -> 2459 passed, 4 skipped
- `uv run ruff check src tests`
  -> All checks passed
- `git diff --check`
  -> pass
- `uv run python scripts/check_handoff_facts.py`
  -> OK
- `uv run python scripts/agent_harness_probe.py --strict`
  -> OK (14/14)
- PR 품질 관문
  -> success

인계 브랜치에서:

- `uv run ruff check src tests`
  -> All checks passed
- `uv run pytest -q`는 처음에 2개 테스트가 실패했다. 원인은 `HANDOFF.md`가 아직 #465를 최신
  main으로 가리킨 것이며, 이 handoff가 고치는 낡은 HANDOFF 실패다.
- 이 handoff 갱신 뒤 `uv run python scripts/check_handoff_facts.py`
  -> OK
- 이 handoff 갱신 뒤 `uv run python scripts/agent_harness_probe.py --strict`
  -> OK (14/14)
- 이 handoff 갱신 뒤 `uv run pytest -q`
  -> 2459 passed, 4 skipped

## 다음 세션 한 줄

스펙 090은 `candidate-source-diversification-sidecar-bottleneck`을 완료로 닫았고, 최신 autonomous-work
sidecar는 `candidate-autonomous-growth-objective-calibration`을 다음 실행 후보로 발행했다. 다음 세션은
`/sync` 후 이 후보를 SDD 기준으로 이어가면 된다.
