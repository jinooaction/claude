# Quickstart: 운영자 대시보드와 모바일 알림 루프

## 로컬 재현

```bash
tmpdir="$(mktemp -d)"
uv run python scripts/operator_status_probe.py --manifest
uv run python scripts/operator_status_probe.py \
  --evidence-dir "$tmpdir" \
  --now 2026-07-02T09:25:00Z \
  --json-out "$tmpdir/operator_status.json" \
  --summary-out "$tmpdir/LAST_RUN.md"
cat "$tmpdir/LAST_RUN.md"
```

## 모바일 상태판 생성

```bash
tmpdir="$(mktemp -d)"
uv run python scripts/generate_mobile_status.py \
  --sidecar-dir "$tmpdir" \
  --output "$tmpdir/status.html" \
  --now 2026-07-02T09:25:00Z
```

생성된 HTML에는 `status-data`와 `operator-status-data` JSON script가 있어야 한다.

## workflow 이후 확인

```bash
git fetch origin automation/operator-status-last-run
git show origin/automation/operator-status-last-run:LAST_RUN.md
git show origin/automation/operator-status-last-run:operator_status.json
```

## 안전 확인

- Telegram 비밀값이 없으면 `send_status=SKIPPED_MISSING_SECRETS`가 정상이다.
- 이 루프는 주문, 자본, live 설정, 서버 SSH, trading worker restart를 수행하지 않는다.
- 상태판은 GitHub Pages 정적 HTML이며 broker와 서버 DB에 접근하지 않는다.
