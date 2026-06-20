# Data Model: Agent Harness Evaluation

## HarnessControl

- `id`: 통제 식별자. 예: `codex_hooks_order`.
- `title`: 사람이 읽는 통제 이름.
- `severity`: `required` 또는 `advisory`.
- `status`: `PASS` 또는 `FAIL`.
- `evidence`: 통과 또는 실패를 재현할 수 있는 파일·문구 근거.
- `message`: 왜 이 통제가 중요한지 또는 왜 실패했는지.

### Validation Rules

- `required` 통제가 하나라도 실패하면 strict 모드는 비정상 종료한다.
- `evidence`는 비어 있으면 안 된다.

## EvaluationTask

- `id`: `HARNESS-001` 형식의 고유 ID.
- `title`: 과제 제목.
- `risk_grade`: 0~4 정수.
- `prompt`: 에이전트에게 줄 수 있는 작업 설명.
- `expected_controls`: 이 과제가 검증해야 하는 통제 범주 목록.
- `success_criteria`: 과제 성공 여부를 판단할 기준 목록.

### Validation Rules

- ID는 중복될 수 없다.
- 위험 등급 0~4가 과제 묶음 전체에서 모두 덮여야 한다.
- 필수 통제 범주가 과제 묶음 전체에서 모두 덮여야 한다.
- 각 과제는 성공 기준을 하나 이상 가져야 한다.

## HarnessReport

- `status`: 전체 판정. 모든 필수 통제가 통과하면 `OK`, 아니면 `DEGRADED`.
- `score`: 통과한 통제 수.
- `max_score`: 전체 필수 통제 수.
- `controls`: `HarnessControl` 목록.
- `task_suite`: 평가 과제 묶음 요약.

## PRHarnessEvidence

- `harness_value`: PR 본문 `- 하네스 평가:` 줄의 값.
- `selected_risk_grade`: PR 본문에서 선택된 위험 등급.

### Validation Rules

- 등급 2 이상은 `scripts/agent_harness_probe.py --strict` 실행 증거를 포함해야 한다.
- 등급 0~1은 값이 비어 있지 않으면 `해당 없음`도 허용한다.
