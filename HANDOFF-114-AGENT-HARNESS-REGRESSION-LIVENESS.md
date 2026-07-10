# HANDOFF-114 — Agent Harness Regression Liveness Contract

## 한 줄 결론

스펙 110은 agent harness 회귀 방어를 후보 단위의 읽기 전용 PASS/WAIT/FAIL 계약으로 닫았고, 완료 뒤 다음 자율 후보를 `candidate-operator-report-liveness-contract`로 전진시켰다.

## main 상태

- 코드 머지: PR #507, merge commit `b364c168151eb6acd954006f785a128b90451a54`.
- 기능 커밋: `858d7ac6ee6980c22acfb0526e36004f46b31b47`.
- 직전 main: `f458e692e176da150f928780111ad82da80ed510`.
- 기능 브랜치: `Codex/110-agent-harness-regression-liveness-contract`.
- handoff 갱신 브랜치: `Codex/110-agent-harness-regression-liveness-contract-handoff`.

## 무엇을 만들었나

- `src/auto_invest/analytics/agent_harness_regression_liveness.py`
  - `scripts/agent_harness_probe.py`, evaluation/quality/redteam TOML, supplied strict output, released-work evidence를 읽어 `CONTRACT_READY`, `OBSERVATION_WAIT`, `BLOCKED`를 판단한다.
  - 기존 `agent_harness_probe.py` evaluator 함수를 재사용하므로 하네스 범주 규칙이 중복되지 않는다.
- `scripts/agent_harness_regression_liveness_probe.py`
  - JSON/Markdown 출력, `--json-out`, `--summary-out`, `--strict-output`, `--released-work`, `--evidence-dir`를 지원한다.
- `src/auto_invest/analytics/autonomous_work_execution.py`
  - 새 다음 후보 `candidate-operator-report-liveness-contract`를 agent-ops frontier에 추가했다.
  - agent-ops source refs에 `AGENTS.md`, `CLAUDE.md`, `.codex/quality-gate.md`, `.github/pull_request_template.md`를 포함시켜 운영 보고 계약의 입력 표면을 드러냈다.
- `specs/110-agent-harness-regression-liveness-contract/`
  - spec, plan, research, data-model, quickstart, contract, checklist, tasks를 추가했다.

## 핵심 판정

- pre-release probe:
  - static harness source: PASS
  - suite coverage: PASS
  - strict output observation: PASS
  - released-work completion: WAIT
  - overall: `OBSERVATION_WAIT`
- released-work local replay:
  - overall: `CONTRACT_READY`
  - completed candidate: `candidate-agent-harness-regression-liveness-contract`
  - next candidate: `candidate-operator-report-liveness-contract`
- autonomous-work local replay:
  - overall: `EXECUTION_READY`
  - selected work: `candidate-operator-report-liveness-contract`
  - risk grade: 2
  - safety impact: none

## post-merge evidence

- `Deploy on merge to main` run `29103143841`: success.
- Deploy job `86396844154`: success; all listed job steps succeeded.
- `Released work ledger` run `29103143824`: success.
- `Autonomous work execution loop` run `29103143807`: success.
- released-work sidecar:
  - commit `b364c168151eb6acd954006f785a128b90451a54`
  - `overall_status=OK`
  - `released_count=31`
  - includes `candidate-agent-harness-regression-liveness-contract`
- autonomous-work sidecar:
  - selected work `candidate-operator-report-liveness-contract`
  - `overall_status=EXECUTION_READY`
  - `autonomy_level=CODEX_AUTONOMOUS_START`
  - `risk_grade=2`
  - safety impact none

## 검증

- focused pytest:
  - `uv run pytest tests/unit/test_agent_harness_regression_liveness.py tests/integration/test_agent_harness_regression_liveness_probe.py tests/unit/test_autonomous_work_execution.py -k 'agent_harness or operator_report'`
  - 10 passed, 35 deselected.
- full pytest:
  - `uv run pytest`
  - 2586 passed, 4 skipped.
- merge 직전 full pytest:
  - `uv run pytest`
  - 2586 passed, 4 skipped.
- lint:
  - `uv run ruff check src tests`
  - All checks passed.
- `git diff --check`: 통과.
- `uv run python scripts/check_handoff_facts.py`: OK.
- `uv run python scripts/agent_harness_probe.py --strict`: OK (14/14).
- PR 품질 관문:
  - local `scripts/check_pr_quality_gate.py /tmp/pr-body-110.md`: `pr-quality-gate-ok`
  - GitHub PR #507 quality gate runs `29102995626`, `29103049972`: success.

## 안전 경계

- 등급 2 운영 체계 변경이다.
- 주문, 브로커 실주문 API, 주문 재시도, 자본 증액, 자본 배분, whitelist/caps 확대, live 전략 교체, live sentinel, 헌법, 커널 목록, K1/K2/K4/K5/K6, 비밀값, 외부 유료 서비스 변경 없음.
- 돈 경로는 계속 `PREVIEW_ONLY`다.
- 이 배포는 dry-run worker 코드 반영이며 실거래 전환이 아니다.

## 다음 후보

다음 자율 후보는 `candidate-operator-report-liveness-contract`다. 목표는 운영자가 "그래서 뭘 했다는 거야?"를 다시 묻지 않도록 `AGENTS.md` 보고 기준, `.codex/quality-gate.md`, PR 템플릿, `QUALITY-006`, HANDOFF, released-work 증거를 하나의 PASS/WAIT/FAIL 계약으로 닫는 것이다.

## 남은 관찰

- HANDOFF-only PR이 머지된 뒤 `check_handoff_facts.py`가 handoff-only 첫 부모 baseline으로 OK인지 확인한다.
- 다음 autonomous-work sidecar가 계속 `candidate-operator-report-liveness-contract`를 선택하는지 확인한다.
- 서버 audit_log는 이 컨테이너에서 직접 확인하지 못한다.
