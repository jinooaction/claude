# HANDOFF 093 — 정적 후보 템플릿 밖 증거 기반 후보 공간 확장 (2026-07-03 KST)

main 코드 베이스라인: `b243a06`(PR #465). 이 작업은 upstream autonomous-evolution loop가
정적 후보 9개를 모두 닫힌 상태로 인식하면 기존 sidecar와 learning ledger 증거에서 새 후보를
합성하게 만든 등급 2 운영 자동화 보정이다.

## 무엇이 바뀌었나

- `src/auto_invest/analytics/evolution_loop.py`
  - `released-work`와 `capital-path-readiness`를 autonomous evolution 입력 sidecar로 추가했다.
  - `released-work`가 완료로 기록한 후보는 upstream 후보 backlog에서도 `released`로 닫힌다.
  - 안전 실행 후보와 operator review/safety-impact 후보가 없을 때만
    `candidate-source-diversification-sidecar-bottleneck`을 만든다.
  - 새 후보 이유에는 released-work 완료 수, learning ledger 결정 수, promotion failure 수,
    capital-path 관찰 병목 수, stale/missing sidecar 수가 들어간다.
- `tests/unit/test_evolution_loop.py`
  - 정적 후보가 모두 닫힌 입력에서 source diversification 후보가 생성되는지 검증한다.
  - 기존 안전 실행 후보가 있을 때 새 후보가 끼어들지 않는지 검증한다.
  - ledger와 관찰 병목 신호가 후보 이유에 들어가는지 검증한다.
- `tests/integration/test_evolution_loop_probe.py`
  - `evolution_loop_probe.py --manifest`가 새 sidecar 입력을 노출하는지 검증한다.
  - probe가 닫힌 정적 후보 입력에서 `candidate-source-diversification-sidecar-bottleneck`을
    `candidate_backlog.json`에 쓰는지 검증한다.
- `specs/089-evolution-source-diversification/`
  - SDD 산출물, quickstart, contract, tasks를 남겼다.
  - 완료 marker: `completed_candidate_id: candidate-evolution-source-diversification`.

## 운영상 의미

- 자율 성장 루프의 upstream 후보 생산자가 더 이상 고정 템플릿 9개만 반복하지 않는다.
- downstream 자율 작업 실행기가 이미 닫은 후보 상태를 upstream에서도 읽어 후보 공간 포화를 직접
  인식한다.
- `candidate-evolution-source-diversification` 자체는 released-work 장부에서 `released`로 닫혔다.
- 최신 autonomous-evolution sidecar는 새 실행 후보를
  `candidate-source-diversification-sidecar-bottleneck`으로 발행했다.
- 같은 push에서 autonomous-work sidecar는 evolution sidecar 갱신 전 입력을 읽어
  `candidate-autonomous-growth-objective-calibration`을 선택했다. 최신 sidecar들을 로컬 재현하면
  `candidate-source-diversification-sidecar-bottleneck`이 `EXECUTION_READY`다.
- 이 변경은 후보 생성과 보고만 바꾼다. 주문, 자본, live 전략, whitelist/caps, 비밀값, 헌법,
  커널 목록은 바꾸지 않았다.

## 배포 후 실제 실행 증거

- PR #465 merge commit: `b243a06e77a04361a8c052b7f0a31cf2768389c7`
- PR #465 feature commit: `c67fda4`
- PR #465 post-merge runs:
  - `Deploy on merge to main` run `28639386244`: success
  - `Autonomous evolution loop` run `28639386349`: success
  - `Autonomous work execution loop` run `28639386220`: success
  - `Released work ledger` run `28639386219`: success
  - `Execution quality package` run `28639386186`: success
- 최신 evolution sidecar:
  - commit `b243a06`
  - safe_high_leverage_work `candidate-source-diversification-sidecar-bottleneck`
  - status_counts: `new=1`, `rejected=2`, `released=7`
- 최신 released-work sidecar:
  - commit `b243a06`
  - released_count 10
  - `candidate-evolution-source-diversification` status `released`
- 최신 sidecar 로컬 재현:
  - selected `candidate-source-diversification-sidecar-bottleneck`
  - status `EXECUTION_READY`
  - risk_grade 2

## 안전 경계

- 위험 등급: 2(운영 자동화 후보 생성 보정)
- 실제 주문 실행: 없음
- 브로커 실주문 API 호출: 없음
- 자본 증액, 자본 배분, 허용 종목 확대, 포지션 한도 완화, live 전략 교체, live sentinel 변경: 없음
- 헌법, 커널 목록, 주문 제한, 감사 로그 schema, 비밀값 저장, 외부 유료 서비스 변경: 없음
- 현재 돈 경로는 계속 `PREVIEW_ONLY`다.

## 검증

PR #465 머지 전:

- `uv run pytest tests/unit/test_evolution_loop.py tests/integration/test_evolution_loop_probe.py -q`
  -> 43 passed
- 실제 sidecar quickstart replay
  -> `candidate-source-diversification-sidecar-bottleneck` 생성
- `uv run python scripts/released_work_probe.py --repo-root . --run-id local-089 --commit "$(git rev-parse HEAD)" --json-out /tmp/released_work_089.json --summary-out /tmp/released_work_089.md`
  -> `candidate-evolution-source-diversification` released
- `uv run pytest`
  -> 2458 passed, 4 skipped
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
- `uv run pytest -q`는 처음에 2개 테스트가 실패했다. 원인은 `HANDOFF.md`가 아직 #463을 최신
  main으로 가리킨 것이며, 이 handoff가 고치는 낡은 HANDOFF 실패다.
- `HANDOFF.md`를 #465 main 기준으로 갱신한 뒤 `uv run python scripts/check_handoff_facts.py`
  -> OK
- `HANDOFF.md`를 #465 main 기준으로 갱신한 뒤 `uv run python scripts/agent_harness_probe.py --strict`
  -> OK (14/14)
- `HANDOFF.md`를 #465 main 기준으로 갱신한 뒤 `uv run pytest -q`
  -> 2458 passed, 4 skipped

## 다음 세션 한 줄

스펙 089은 `candidate-evolution-source-diversification`을 완료로 닫았고, 최신 evolution sidecar는
`candidate-source-diversification-sidecar-bottleneck`을 새 safe_high_leverage_work로 발행했다. 다음
세션은 `/sync` 후 최신 sidecar 재현 또는 다음 autonomous-work 실행을 확인하고 이 후보를 SDD 기준으로
이어가면 된다.
