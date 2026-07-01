# 빠른 확인: 자율 작업 실행 루프

## 로컬 smoke

```bash
tmpdir=$(mktemp -d)
uv run python scripts/autonomous_work_execution_probe.py --manifest > /tmp/awe-manifest.tsv
while IFS=$'\t' read -r key branch filename; do
  git fetch --depth=1 origin "${branch}" || true
  git show "origin/${branch}:${filename}" > "${tmpdir}/${key}.md" 2>/dev/null || true
done < /tmp/awe-manifest.tsv
uv run python scripts/autonomous_work_execution_probe.py \
  --evidence-dir "${tmpdir}" \
  --json-out /tmp/autonomous_work_execution.json \
  --summary-out /tmp/autonomous_work_execution.md \
  --json
```

## sidecar 확인

```bash
git fetch origin automation/autonomous-work-execution-last-run
git show origin/automation/autonomous-work-execution-last-run:LAST_RUN.md
git show origin/automation/autonomous-work-execution-last-run:autonomous_work_execution.json
```

## 기대 결과

- `selected_work`가 존재하거나, 안전한 후보가 없으면 그 이유가 `overall_status`와 Markdown에 표시된다.
- 위험 후보는 `OPERATOR_APPROVAL_REQUIRED`로 분리된다.
- 실제 주문, 자본 배분, live 설정 변경은 발생하지 않는다.
