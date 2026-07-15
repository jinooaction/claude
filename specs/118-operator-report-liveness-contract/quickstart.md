# Quickstart: Operator Report Liveness Contract

## Focused report check

```bash
tmpdir="$(mktemp -d)"
cat > "$tmpdir/final-report.md" <<'EOF'
운영자가 바로 이해할 수 있게 완료 보고의 의미 검사가 main에 들어갔다.

무엇을 고쳤는가: 최종 보고가 실제 운영 상태 변화, 검증, 남은 위험을 담는지 읽기 전용으로 검사한다.
돈 경로와 안전 경계: 주문, 자본, whitelist/caps, 비밀값은 건드리지 않았다. 다음 세션은 released-work가 이 후보를 소비하면 같은 작업을 반복하지 않는다.
검증: focused pytest, 전체 pytest, ruff, handoff 사실 검증, strict harness로 확인한다.
남은 위험: 실제 서버와 KIS 계좌 상태는 이 보고서의 범위 밖이다.
EOF
cat > "$tmpdir/released_work.json" <<'EOF'
{"released_work":[{"candidate_id":"candidate-operator-report-liveness-contract","status":"released"}]}
EOF
uv run python scripts/operator_report_liveness_probe.py \
  --repo-root . \
  --final-report "$tmpdir/final-report.md" \
  --released-work "$tmpdir/released_work.json" \
  --format json \
  --json-out "$tmpdir/operator_report_liveness.json" \
  --summary-out "$tmpdir/operator_report_liveness.md"
```

Expected: JSON `overall_status` is `CONTRACT_READY`.

## Tests

```bash
uv run pytest tests/unit/test_operator_report_liveness.py -q
uv run pytest tests/integration/test_operator_report_liveness_probe.py -q
uv run pytest tests/unit/test_autonomous_work_execution.py -q
```

## Safety

This probe is read-only. It must not call GitHub, KIS, SSH, paid services, order paths, capital paths, secret stores, or modify repository files.
