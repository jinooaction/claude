# 빠른 확인: 완료 후보 소비 및 차순위 자동 승격 루프

## 완료 장부 로컬 생성

```bash
uv run python scripts/released_work_probe.py --repo-root . --json
```

기대:

- `released_work`에 `candidate-fd04772a23c5`가 포함된다.
- `source_spec`은 `specs/078-money-gate-alignment-loop`이다.

## 자율 작업 실행 루프에서 완료 후보 제외 확인

```bash
tmpdir="$(mktemp -d)"
uv run python scripts/autonomous_work_execution_probe.py --manifest | while IFS=$'\t' read -r key ref file; do
  git show "origin/$ref:$file" > "$tmpdir/$key.md" 2>/dev/null || true
done
uv run python scripts/autonomous_work_execution_probe.py \
  --evidence-dir "$tmpdir" \
  --repo-root . \
  --json | jq '.selected_work.candidate_id, [.suppressed_work[] | select(.status=="RELEASED") | .candidate_id]'
```

기대:

- `candidate-fd04772a23c5`는 `suppressed_work`에서 `RELEASED`다.
- `selected_work`는 다음 실행 가능 후보로 이동한다.

## 안전 확인

```bash
uv run pytest tests/unit/test_released_work.py tests/unit/test_autonomous_work_execution.py \
  tests/integration/test_released_work_probe.py tests/integration/test_autonomous_work_execution_probe.py
uv run ruff check src/auto_invest/analytics/released_work.py scripts/released_work_probe.py \
  src/auto_invest/analytics/autonomous_work_execution.py scripts/autonomous_work_execution_probe.py \
  tests/unit/test_released_work.py tests/integration/test_released_work_probe.py
```
