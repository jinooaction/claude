#!/usr/bin/env bash
# 가드형 라이브 캐너리 전환 스크립트 (헌법 X.4 v4.0.0 "가드형 go-live 채널").
#
# 서버에서 root 로 실행된다 — go-live-canary.yml 워크플로우가 SSH 로
#   `sudo bash -s < deploy/go-live-canary.sh`
# 처럼 파이프한다. 새 배포 로직을 만들지 않는다: .env 의 AUTO_INVEST_MODE 한 줄만
# live 로 바꾸고 워커를 재시작한 뒤, 헬스체크에 실패하면 dry-run 으로 자동 복구한다.
#
# 안전 경계 (헌법 X.4):
#   - 라이브 캐너리까지만 — 모드를 live 로 바꾸고, 센티넬에 지정된 경우 캐너리
#     자본(capital_usd)과 축소 룰셋(rules_path, CANARY 스테이지)도 적용한다. K1 캡은
#     룰셋 caps 가 천장. 풀라이브 승격이 아니다(스테이지는 CANARY 그대로).
#   - 장중에는 전환 보류 (헌법 VIII.A) — XNYS 정규장이 열려 있으면 .env 를 건드리지
#     않고 deferred 로 끝낸다(워커 재시작이 장중 주문 관리를 깨지 않도록).
#   - 실패 시 dry-run 자동 복구 — 워커가 live 로 안 뜨면 즉시 되돌린다.
#   - 멱등 — 이미 live 면 재시작·헬스체크만 다시 한다.
#
# 마지막 줄에 `GO_LIVE_RESULT=<상태>` 를 출력한다(워크플로우가 파싱):
#   armed_live_canary | deferred_market_open | reverted_dry_run

set -euo pipefail

ENV_FILE=/opt/auto-invest/.env
APP_DIR=/opt/auto-invest
UV=/usr/local/bin/uv
EXPECTED_SHA="${EXPECTED_SHA:-}"
tmp_env=""

cleanup() {
    if [[ -n "${tmp_env:-}" && -f "$tmp_env" ]]; then
        rm -f "$tmp_env"
    fi
}
trap cleanup EXIT

set_env_value() {
    local file="$1"
    local key="$2"
    local value="$3"
    if grep -qE "^${key}=" "$file"; then
        sed -i "s#^${key}=.*#${key}=${value}#" "$file"
    else
        printf '%s=%s\n' "$key" "$value" >> "$file"
    fi
}

if [[ ! -f "$ENV_FILE" ]]; then
    echo "[go-live] $ENV_FILE 없음 — 인스턴스가 프로비저닝되지 않았습니다." >&2
    echo "GO_LIVE_RESULT=no_env_file"
    exit 1
fi

# 0) 서버 repo 를 origin/main 으로 동기화(새 룰셋·센티넬 파일 반영). kis-smoke 패턴 —
#    deploy-on-merge 타이밍에 의존하지 않도록 스크립트가 직접 최신 코드를 끌어온다.
cd "$APP_DIR" 2>/dev/null || { echo "GO_LIVE_RESULT=no_app_dir"; exit 1; }
git config --global --add safe.directory "$APP_DIR" 2>/dev/null || true
sudo -u auto-invest git config --global --add safe.directory "$APP_DIR" 2>/dev/null || true
if ! sudo -u auto-invest git fetch --quiet origin main 2>/dev/null; then
    echo "[go-live] origin/main fetch 실패 — 검증 불능 상태라 전환 중단." >&2
    echo "GO_LIVE_RESULT=repo_sync_failed"
    exit 1
fi
if ! sudo -u auto-invest git reset --hard origin/main 2>/dev/null; then
    echo "[go-live] origin/main reset 실패 — 어떤 코드가 실행될지 확정할 수 없어 전환 중단." >&2
    echo "GO_LIVE_RESULT=repo_sync_failed"
    exit 1
fi
current_sha="$(git rev-parse HEAD)"
echo "[go-live] server repo @ ${current_sha}"
if [[ -n "$EXPECTED_SHA" && "$current_sha" != "$EXPECTED_SHA" ]]; then
    echo "[go-live] GITHUB_SHA(${EXPECTED_SHA}) 와 서버 HEAD(${current_sha}) 불일치 — 전환 중단." >&2
    echo "GO_LIVE_RESULT=revision_mismatch"
    exit 1
fi

# 0b) 센티넬에서 원하는 자본/룰셋 읽기(선택 — 운영자 선택 1번 "포지션 축소 + 중간 자본").
#     없으면 .env 기존값을 유지한다(모드만 바뀜).
REQ_FILE="$APP_DIR/automation/go-live-canary.request"
want_capital=""
want_rules=""
if [[ -f "$REQ_FILE" ]]; then
    want_capital="$(grep -E '^capital_usd:' "$REQ_FILE" | head -1 | awk '{print $2}' || true)"
    want_rules="$(grep -E '^rules_path:' "$REQ_FILE" | head -1 | awk '{print $2}' || true)"
fi
if [[ -n "$want_capital" && ! "$want_capital" =~ ^[0-9]+([.][0-9]{1,2})?$ ]]; then
    echo "[go-live] invalid capital_usd=${want_capital@Q} — 전환 중단." >&2
    echo "GO_LIVE_RESULT=invalid_request"
    exit 1
fi
if [[ -n "$want_rules" ]]; then
    if [[ ! "$want_rules" =~ ^config/[A-Za-z0-9._/-]+[.]toml$ || "$want_rules" == *".."* ]]; then
        echo "[go-live] invalid rules_path=${want_rules@Q} — 전환 중단." >&2
        echo "GO_LIVE_RESULT=invalid_request"
        exit 1
    fi
    if [[ ! -f "$APP_DIR/$want_rules" ]]; then
        echo "[go-live] requested rules_path not found: ${want_rules}" >&2
        echo "GO_LIVE_RESULT=invalid_request"
        exit 1
    fi
fi

# 1) 장중 가드 (헌법 VIII.A). XNYS 정규장이 열려 있으면 전환 보류.
market_state="$(
    cd "$APP_DIR" 2>/dev/null && \
    sudo -u auto-invest UV_CACHE_DIR="$APP_DIR/.cache/uv" "$UV" run python - <<'PY' 2>/dev/null
import datetime as dt
try:
    import exchange_calendars as ec
    cal = ec.get_calendar("XNYS")
    now = dt.datetime.now(dt.timezone.utc)
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
if [[ "$market_state" != "CLOSED" ]]; then
    echo "[go-live] 시장 상태가 CLOSED 로 확인되지 않음(${market_state}) — 전환 중단."
    echo "GO_LIVE_RESULT=market_state_unknown"
    exit 1
fi

# 2) 현재 모드 스냅샷 + 백업.
current_mode="$(grep -E '^AUTO_INVEST_MODE=' "$ENV_FILE" | head -1 | cut -d= -f2- || true)"
cp -a "$ENV_FILE" "${ENV_FILE}.pre-golive.bak"
echo "[go-live] 현재 AUTO_INVEST_MODE=${current_mode:-unset} → live 로 전환(캐너리 룰셋·자본 유지)."

# 3) live 로 전환할 .env 후보를 먼저 완성한 뒤 같은 파일시스템에서 원자 교체.
tmp_env="$(mktemp "$(dirname "$ENV_FILE")/.env.golive.XXXXXX")"
cp "$ENV_FILE" "$tmp_env"
chown --reference="$ENV_FILE" "$tmp_env"
chmod --reference="$ENV_FILE" "$tmp_env"
set_env_value "$tmp_env" AUTO_INVEST_MODE live

# 3b) 캐너리 자본/룰셋 적용 (센티넬에 지정된 경우만 — 운영자 선택 1번).
#     per-trade 캡(룰셋 caps)과 자본이 함께 노출 상한을 정한다. 룰셋은 CANARY 스테이지.
if [[ -n "$want_capital" ]]; then
    set_env_value "$tmp_env" AUTO_INVEST_CAPITAL "$want_capital"
    echo "[go-live] AUTO_INVEST_CAPITAL=${want_capital} 적용(중간 자본)."
fi
if [[ -n "$want_rules" ]]; then
    set_env_value "$tmp_env" AUTO_INVEST_RULES "$want_rules"
    echo "[go-live] AUTO_INVEST_RULES=${want_rules} 적용(포지션 축소 룰셋)."
fi
mv -f "$tmp_env" "$ENV_FILE"
tmp_env=""

# 4) 워커 재시작 (EnvironmentFile=.env 를 다시 읽어 live 반영).
restart_epoch="$(date +%s)"
systemctl restart auto-invest.service
echo "[go-live] 워커 재시작 완료 — 헬스 윈도 95초 대기…"
sleep 95

# 5) 헬스체크: 현재(새) 인스턴스 로그만 본다. 재시작은 이전 인스턴스를 종료시키는데,
#    그 종료 트레이스백이 restart_epoch 와 같은 초에 찍혀 윈도에 섞인다 → 마지막
#    "Started ... worker" 마커 이후(=새 인스턴스)만 스캔해 전환기 노이즈를 제외한다.
FATAL_RE='Traceback \(most recent call last\)|CRITICAL|AUTO_INVEST_CAPITAL must be set'
START_RE='Started auto-invest live trading worker'
active="$(systemctl is-active auto-invest.service 2>/dev/null || true)"
post_log="$(journalctl -u auto-invest.service --since "@${restart_epoch}" --no-pager 2>/dev/null || true)"
current_log="$(printf '%s\n' "$post_log" | awk -v re="$START_RE" '$0 ~ re {found=1; buf=""} found {buf=buf $0 ORS} END {printf "%s", buf}')"
if [[ -z "$current_log" ]]; then current_log="$post_log"; fi  # 마커 없으면 폴백.
fatal="$(printf '%s\n' "$current_log" | grep -ciE "$FATAL_RE" || true)"
echo "[go-live] is-active=${active} fatal_log_hits=${fatal:-0} (현재 인스턴스 기준)"
echo "[go-live] --- 현재 인스턴스 journal 발췌(마지막 30줄) ---"
printf '%s\n' "$current_log" | tail -30
if [[ "${fatal:-0}" -ne 0 ]]; then
    echo "[go-live] --- 매칭된 치명 패턴 라인 ---"
    printf '%s\n' "$current_log" | grep -iE "$FATAL_RE" | tail -15
fi
echo "[go-live] --- 발췌 끝 ---"

if [[ "$active" == "active" && "${fatal:-0}" -eq 0 ]]; then
    echo "[go-live] ✅ LIVE-CANARY 무장 완료(mode=live). K1 캡·화이트리스트·서킷브레이커·정합성 그대로 작동."
    echo "GO_LIVE_RESULT=armed_live_canary"
    exit 0
fi

# 6) 실패 → .env 전체 자동 복구.
echo "[go-live] ❌ 헬스체크 실패 — 전환 전 .env 전체 백업으로 자동 복구."
cp -a "${ENV_FILE}.pre-golive.bak" "$ENV_FILE"
systemctl restart auto-invest.service
echo "GO_LIVE_RESULT=reverted_dry_run"
exit 1
