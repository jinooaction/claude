# 빠른 확인: 돈 경로 게이트 정렬 루프

## manifest 확인

```bash
uv run python scripts/money_gate_alignment_probe.py --manifest
```

## 로컬 샘플 실행

```bash
tmpdir=$(mktemp -d)
uv run python scripts/money_gate_alignment_probe.py \
  --evidence-dir "$tmpdir" \
  --json \
  --now 2026-07-01T09:20:00Z
```

## 최신 automation sidecar smoke

```bash
git fetch origin '+refs/heads/automation/*:refs/remotes/origin/automation/*'
tmpdir=$(mktemp -d)
while IFS=$'\t' read -r key branch filename; do
  git show "origin/${branch}:${filename}" > "${tmpdir}/${key}.md" 2>/dev/null || true
done < <(uv run python scripts/money_gate_alignment_probe.py --manifest)
uv run python scripts/money_gate_alignment_probe.py \
  --evidence-dir "$tmpdir" \
  --json-out /tmp/money_gate_alignment.json \
  --summary-out /tmp/money_gate_alignment.md
```

예상 현재 상태: `ALIGNED_WAITING`. 전진 관측 부족은 정상 대기이며 주문·자본 변경은 없다.

## 검증

```bash
uv run pytest tests/unit/test_money_gate_alignment.py tests/integration/test_money_gate_alignment_probe.py
uv run pytest
uv run ruff check src tests
```
