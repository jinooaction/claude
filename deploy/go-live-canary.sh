#!/usr/bin/env bash
# 가드형 라이브 캐너리 전환 스크립트 (헌법 X.4 v4.0.0 "가드형 go-live 채널").
#
# 서버에서 root 로 실행된다 — go-live-canary.yml 워크플로우가 SSH 로
#   `sudo bash -s < deploy/go-live-canary.sh`
# 처럼 파이프한다. 새 배포 로직을 만들지 않는다: .env 의 AUTO_INVEST_MODE 한 줄만
# live 로 바꾸고 워커를 재시작한 뒤, 헬스체크에 실패하면 dry-run 으로 자동 복구한다.
#
# 안전 경계 (헌법 X.4):
#   - 라이브 캐너리까지만 — 룰셋(캐너리)·자본(.env 기본 소액)·K1 캡은 그대로 둔다.
#     이 스크립트는 모드만 바꾼다. 풀라이브 승격이 아니다.
#   - 장중에는 전환 보류 (헌법 VIII.A) — XNYS 정규장이 열려 있으면 .env 를 건드리지
#     않고 deferred 로 끝낸다(워커 재시작이 장중 주문 관리를 깨지 않도록).
#   - 실패 시 dry-run 자동 복구 — 워커가 live 로 안 뜨면 즉시 되돌린다.
#   - 멱등 — 이미 live 면 재시작·헬스체크만 다시 한다.
#
# 마지막 줄에 `GO_LIVE_RESULT=<상태>` 를 출력한다(워크플로우가 파싱):
#   armed_live_canary | deferred_market_open | reverted_dry_run

set -uo pipefail

ENV_FILE=/opt/auto-invest/.env
APP_DIR=/opt/auto-invest
UV=/usr/local/bin/uv

if [[ ! -f "$ENV_FILE" ]]; then
    echo "[go-live] $ENV_FILE 없음 — 인스턴스가 프로비저닝되지 않았습니다." >&2
    echo "GO_LIVE_RESULT=no_env_file"
    exit 1
fi

# 1) 장중 가드 (헌법 VIII.A). XNYS 정규장이 열려 있으면 전환 보류.
market_state="$(
    cd "$APP_DIR" 2>/dev/null && \
    sudo -u auto-invest UV_CACHE_DIR="$APP_DIR/.cache/uv" "$UV" run python - <<'PY' 2>/dev/null
import datetime as dt
try:
    import exchange_calendars as ec
    cal = ec.get_calendar("XNYS")
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M")
    print("OPEN" if cal.is_open_on_minute(now) else "CLOSED")
except Exception:
    print("UNKNOWN")
PY
)"
market_state="${market_state:-UNKNOWN}"
echo "[go-live] market_state=${market_state}"

if [[ "$market_state" == "OPEN" ]]; then
    echo "[go-live] 미국 정규장 개장 중 — 헌법 VIII.A 로 전환을 장 마감 후로 보류. .env 무변경."
    echo "GO_LIVE_RESULT=deferred_market_open"
    exit 0
fi

# 2) 현재 모드 스냅샷 + 백업.
current_mode="$(grep -E '^AUTO_INVEST_MODE=' "$ENV_FILE" | head -1 | cut -d= -f2- || true)"
cp -a "$ENV_FILE" "${ENV_FILE}.pre-golive.bak"
echo "[go-live] 현재 AUTO_INVEST_MODE=${current_mode:-unset} → live 로 전환(캐너리 룰셋·자본 유지)."

# 3) live 로 전환 (모드 한 줄만 — 최소 편집).
if grep -qE '^AUTO_INVEST_MODE=' "$ENV_FILE"; then
    sed -i 's/^AUTO_INVEST_MODE=.*/AUTO_INVEST_MODE=live/' "$ENV_FILE"
else
    echo 'AUTO_INVEST_MODE=live' >> "$ENV_FILE"
fi

# 4) 워커 재시작 (EnvironmentFile=.env 를 다시 읽어 live 반영).
restart_epoch="$(date +%s)"
systemctl restart auto-invest.service
echo "[go-live] 워커 재시작 완료 — 헬스 윈도 95초 대기…"
sleep 95

# 5) 헬스체크: 재시작 시점 이후 로그만 본다(이전 인스턴스/전환기 노이즈 제외).
FATAL_RE='Traceback \(most recent call last\)|CRITICAL|AUTO_INVEST_CAPITAL must be set'
active="$(systemctl is-active auto-invest.service 2>/dev/null || true)"
post_log="$(journalctl -u auto-invest.service --since "@${restart_epoch}" --no-pager 2>/dev/null || true)"
fatal="$(printf '%s\n' "$post_log" | grep -ciE "$FATAL_RE" || true)"
echo "[go-live] is-active=${active} fatal_log_hits=${fatal:-0} (재시작 이후 기준)"
echo "[go-live] --- 재시작 이후 journal 발췌(마지막 30줄) ---"
printf '%s\n' "$post_log" | tail -30
if [[ "${fatal:-0}" -ne 0 ]]; then
    echo "[go-live] --- 매칭된 치명 패턴 라인 ---"
    printf '%s\n' "$post_log" | grep -iE "$FATAL_RE" | tail -15
fi
echo "[go-live] --- 발췌 끝 ---"

if [[ "$active" == "active" && "${fatal:-0}" -eq 0 ]]; then
    echo "[go-live] ✅ LIVE-CANARY 무장 완료(mode=live). K1 캡·화이트리스트·서킷브레이커·정합성 그대로 작동."
    echo "GO_LIVE_RESULT=armed_live_canary"
    exit 0
fi

# 6) 실패 → dry-run 자동 복구.
echo "[go-live] ❌ 헬스체크 실패 — dry-run 으로 자동 복구."
sed -i 's/^AUTO_INVEST_MODE=.*/AUTO_INVEST_MODE=dry-run/' "$ENV_FILE"
systemctl restart auto-invest.service
echo "GO_LIVE_RESULT=reverted_dry_run"
exit 1
