#!/usr/bin/env bash
# auto-invest 자율 튜너 진입점 (systemd auto-invest-tune.service ExecStart에서 호출).
#
# 이미 검증·머지된 스펙 005 CLI `auto-invest tune --apply` 를 그대로 실행한다.
# 새 로직을 만들지 않는다 — 언제 돌릴지(장 마감 후 1회)를 systemd 타이머에
# 맡길 뿐이다. 적용 안전성은 전부 튜너 자신이 보장한다:
#   - 저위험 L1(tier_b 임계값 조이기) 한 종류만 자동 적용, 가역.
#   - 장 시간 마진 안이면 0건 적용(헌법 VIII.A, 게이트가 한 번 더 막음).
#   - 윈도 표본 < 최소 표본이면 거부(헌법 X).
#   - 세션 날짜 기준 멱등 — 같은 날 두 번 돌려도 한 번만 적용.
#   - 대상이 kernel.toml 에 닿으면 무조건 L4(자동 적용 거부).

set -euo pipefail

cd "$(dirname "$0")/.."

db="${AUTO_INVEST_DB:-data/auto_invest.db}"
reports="${AUTO_INVEST_REPORTS:-reports}"

# Fail-safe: 텔레메트리 DB가 아직 없으면(워커가 한 번도 안 돈 새 인스턴스)
# 튜닝할 측정치가 없으므로 조용히 성공 종료한다. 매일 빨간 X 를 만들지 않는다
# ('worker is fail-safe until KIS keys set' 와 같은 철학).
if [[ ! -f "$db" ]]; then
    echo "[run-tune.sh] telemetry DB not found at $db — nothing to tune yet, skipping." >&2
    exit 0
fi

echo "[run-tune.sh] running autonomous tuner (L1 apply, off-hours) db=$db reports=$reports" >&2
exec uv run auto-invest tune --apply \
    --db "$db" \
    --output-root "$reports"
