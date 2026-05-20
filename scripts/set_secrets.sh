#!/usr/bin/env bash
# auto-invest — KIS 자격증명을 인스턴스의 .env에 한 번에 채워넣는 도구.
#
# Vultr 인스턴스의 웹 콘솔로 root 로그인 후 다음 한 줄만 실행:
#
#   bash /opt/auto-invest/scripts/set_secrets.sh
#
# 그러면 다음 세 가지 prompt가 차례로 떠서 KIS 자격증명을 받습니다.
# 입력값은 화면에 표시되지 않고(비밀번호 마스킹), .env(chmod 0600)에만
# 저장되며, 이 스크립트는 로그/journal/콘솔 어디에도 값을 echo하지 않습니다.
# 입력 후 워커가 자동으로 재시작됩니다.

set -euo pipefail

ENV_PATH="${ENV_PATH:-/opt/auto-invest/.env}"
WORKER_UNIT="${WORKER_UNIT:-auto-invest.service}"

if [[ ! -f "$ENV_PATH" ]]; then
    echo "ERROR: $ENV_PATH 파일이 없습니다. cloud-init이 먼저 실행되어야 합니다." >&2
    exit 2
fi

echo "=========================================================="
echo "auto-invest 비밀키 입력 도구"
echo
echo "다음 네 가지 값을 차례로 입력하세요."
echo "  - KIS Developers 앱 키"
echo "  - KIS Developers 앱 시크릿"
echo "  - 미국 주식 거래 가능한 KIS 계좌번호"
echo "  - Anthropic API 키 (auto-invest design 자동 룰 설계용; 비워두면 design 명령만 안 됨)"
echo
echo "입력은 화면에 표시되지 않습니다 (비밀번호처럼 마스킹)."
echo "값은 $ENV_PATH (chmod 0600) 에만 저장되고, 로그에는 절대 남지 않습니다."
echo "=========================================================="
echo

read -rsp "KIS_APP_KEY: " kis_app_key
echo
if [[ -z "$kis_app_key" ]]; then
    echo "ERROR: KIS_APP_KEY가 비어 있습니다." >&2
    exit 3
fi

read -rsp "KIS_APP_SECRET: " kis_app_secret
echo
if [[ -z "$kis_app_secret" ]]; then
    echo "ERROR: KIS_APP_SECRET가 비어 있습니다." >&2
    exit 3
fi

read -rsp "KIS_ACCOUNT_NO (계좌번호): " kis_account_no
echo
if [[ -z "$kis_account_no" ]]; then
    echo "ERROR: KIS_ACCOUNT_NO가 비어 있습니다." >&2
    exit 3
fi

# Anthropic API 키는 선택 — 비워두면 design 명령만 안 됨, 실거래 워커는 정상 동작.
read -rsp "ANTHROPIC_API_KEY (Enter만 누르면 건너뛰기): " anthropic_api_key
echo

# .env 백업 (만일을 위해, 권한은 유지)
cp -p "$ENV_PATH" "${ENV_PATH}.bak.$(date +%Y%m%d-%H%M%S)"

# 세 키를 in-place 갱신. 기존 라인이 있으면 교체, 없으면 추가.
# sed의 구분자를 |로 써서 값 안에 슬래시가 있어도 안전하게 처리.
update_key() {
    local key="$1"
    local value="$2"
    if grep -qE "^${key}=" "$ENV_PATH"; then
        # 기존 줄 교체
        # shellcheck disable=SC2016
        sed -i "s|^${key}=.*|${key}=${value}|" "$ENV_PATH"
    else
        echo "${key}=${value}" >> "$ENV_PATH"
    fi
}

update_key "KIS_APP_KEY" "$kis_app_key"
update_key "KIS_APP_SECRET" "$kis_app_secret"
update_key "KIS_ACCOUNT_NO" "$kis_account_no"
if [[ -n "$anthropic_api_key" ]]; then
    update_key "ANTHROPIC_API_KEY" "$anthropic_api_key"
fi

# 비밀 변수를 메모리에서 즉시 제거.
unset kis_app_key kis_app_secret kis_account_no anthropic_api_key

# 권한 보장
chown auto-invest:auto-invest "$ENV_PATH" 2>/dev/null || true
chmod 0600 "$ENV_PATH"

echo
echo "=========================================================="
echo "비밀키 저장 완료. 워커를 재시작합니다..."
echo

systemctl restart "$WORKER_UNIT"
sleep 2

# Worker가 dry-run 모드면 한 번 검증 후 정상 종료(Type=simple + run-worker.sh의
# dry-run 분기). 그래서 is-active로만 보면 "active 아님"으로 잘못 보임 —
# journalctl을 조회해 "Dry run successful." 또는 ExecStart 정상 종료 흔적을
# 같이 확인한다.
if systemctl is-active --quiet "$WORKER_UNIT"; then
    echo "OK — $WORKER_UNIT 가 정상 가동 중입니다 (live 모드)."
    worker_ok=1
elif journalctl -u "$WORKER_UNIT" -n 30 --no-pager 2>/dev/null \
        | grep -qE "Dry run successful\.|Deactivated successfully\."; then
    echo "OK — $WORKER_UNIT 가 dry-run 검증을 성공적으로 마쳤습니다 (1주일 안전 관찰 단계)."
    echo "   journalctl -u $WORKER_UNIT -n 10 에서 'Dry run successful.' 확인 가능."
    worker_ok=1
else
    worker_ok=0
fi

if [[ "$worker_ok" -eq 1 ]]; then
    echo
    echo "다음 확인 명령:"
    echo "  systemctl status $WORKER_UNIT"
    echo "  journalctl -u $WORKER_UNIT -n 30"
    echo
    echo "1주일 후 실주문 전환 한 줄:"
    echo "  sed -i 's/^AUTO_INVEST_MODE=.*/AUTO_INVEST_MODE=live/' $ENV_PATH \\"
    echo "  && systemctl restart $WORKER_UNIT"
else
    echo "WARNING — 워커가 정상 가동되지 않았고 dry-run 성공 흔적도 없습니다."
    echo "  다음 명령으로 원인 확인:"
    echo "  journalctl -u $WORKER_UNIT -n 50"
    exit 4
fi
echo "=========================================================="
