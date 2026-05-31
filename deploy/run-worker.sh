#!/usr/bin/env bash
# auto-invest 워커 진입점 (systemd ExecStart에서 호출).
#
# AUTO_INVEST_MODE 환경변수 한 줄로 dry-run / live 모드를 토글합니다:
#   AUTO_INVEST_MODE=dry-run  (기본) — 실주문 안 나감, 감사 로그만 쌓임
#   AUTO_INVEST_MODE=live              — 실주문 모드
#
# 1주일 dry-run 관찰 후 실주문 전환은 .env에서 이 한 줄만 바꾸고
# 'systemctl restart auto-invest.service' 한 번이면 됩니다.

set -euo pipefail

cd "$(dirname "$0")/.."

mode="${AUTO_INVEST_MODE:-dry-run}"
rules="${AUTO_INVEST_RULES:-tests/fixtures/rules/sample-canary.toml}"
db="${AUTO_INVEST_DB:-data/auto_invest.db}"
capital="${AUTO_INVEST_CAPITAL:?AUTO_INVEST_CAPITAL must be set (USD integer)}"

# 스펙 029 슬라이스 2 — 자산 인식 유효 자본을 라이브 캐너리에 적용한다.
#   --capital-tracking 만 켠다(--capital-growth 는 일부러 뺀다): 하락은 항상
#   캡을 줄여 방어하고, 상승은 미반영이라 --capital 시작 자본이 캡 천장이다
#   (보수적 시작). K1 캡·화이트리스트는 그대로 — 입력 자본만 살아있는 NAV 를
#   추종한다. NAV 조회 실패는 격리되어 직전 유효 자본을 유지한다(거래 무중단).
if [[ "$mode" == "live" ]]; then
    echo "[run-worker.sh] starting in LIVE mode (capital=$capital, rules=$rules, capital-tracking=on/defense-only)" >&2
    exec uv run auto-invest run \
        --config "$rules" \
        --db "$db" \
        --capital "$capital" \
        --capital-tracking
else
    echo "[run-worker.sh] starting in DRY-RUN mode (no real orders) (capital=$capital, rules=$rules)" >&2
    exec uv run auto-invest run --dry-run \
        --config "$rules" \
        --db "$db" \
        --capital "$capital" \
        --capital-tracking
fi
