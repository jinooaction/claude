#!/usr/bin/env bash
# Vultr cloud-init User-Data — auto-invest 인스턴스 부팅 시 한 번에 실행.
#
# 사용법: Vultr 콘솔에서 인스턴스를 만들 때 "User Data" / "Cloud-Init"
# 필드에 이 파일 전체를 붙여넣고, 아래 CONFIGURE_ME 네 줄의 값을 채우세요.
# 나머지는 부팅과 동시에 자동 실행되어 dry-run 모드로 워커가 가동됩니다.
#
# 1주일 dry-run 관찰 후 실주문 전환:
#   ssh root@<인스턴스IP>
#   sed -i 's/^AUTO_INVEST_MODE=.*/AUTO_INVEST_MODE=live/' /opt/auto-invest/.env
#   systemctl restart auto-invest.service
#
# 안전:
#   - 이 스크립트는 cloud-init이 root로 한 번만 실행합니다.
#   - KIS 키는 인스턴스 내부 /opt/auto-invest/.env (chmod 0600)로만 저장,
#     로그/journal에 절대 echo하지 않습니다.
#   - User-Data 자체는 Vultr 메타데이터에 보관되니, 가동 후 Vultr 콘솔의
#     "Settings → User Data → Edit"에서 KIS 키 줄을 비우는 것도 가능
#     (영구 보관 위험을 줄임 — cloud-init은 이미 실행됐으므로 안전).

set -euo pipefail
exec > >(tee /var/log/auto-invest-cloud-init.log) 2>&1

# ============================================================================
# CONFIGURE_ME — 이 네 줄만 채우세요. 다른 줄은 건드리지 마세요.
# ============================================================================
KIS_APP_KEY="여기에_KIS앱키"
KIS_APP_SECRET="여기에_KIS시크릿"
KIS_ACCOUNT_NO="여기에_계좌번호"
AUTO_INVEST_CAPITAL="100"
# ============================================================================

# 안전: 비밀이 placeholder 그대로면 종료
if [[ "$KIS_APP_KEY" == "여기에_KIS앱키" ]] || [[ -z "$KIS_APP_KEY" ]]; then
    echo "ERROR: KIS_APP_KEY가 채워지지 않았습니다. User-Data를 수정 후 인스턴스를 재생성하세요." >&2
    exit 100
fi

echo "[1/8] 시스템 업데이트 + 기본 도구 설치"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get upgrade -y -qq
apt-get install -y -qq git curl nano build-essential ca-certificates sqlite3

echo "[2/8] 타임존 UTC 설정"
timedatectl set-timezone UTC

echo "[3/8] auto-invest 시스템 계정 생성"
if ! id auto-invest >/dev/null 2>&1; then
    useradd --system --create-home --home-dir /var/lib/auto-invest --shell /bin/bash auto-invest
fi
install -d -m 0750 -o auto-invest -g auto-invest /opt/auto-invest
install -d -m 0750 -o auto-invest -g auto-invest /opt/auto-invest/data
install -d -m 0750 -o auto-invest -g auto-invest /opt/auto-invest/logs

echo "[4/8] uv 설치 (auto-invest 사용자 + 시스템 PATH)"
curl -LsSf https://astral.sh/uv/install.sh | UV_INSTALL_DIR=/usr/local/bin sh
ln -sf /usr/local/bin/uv /usr/bin/uv

echo "[5/8] 저장소 클론 + 의존성 설치"
sudo -u auto-invest git clone https://github.com/jinooaction/claude.git /opt/auto-invest 2>/dev/null || true
cd /opt/auto-invest
sudo -u auto-invest git fetch origin main --quiet
sudo -u auto-invest git checkout main --quiet
sudo -u auto-invest git pull --ff-only --quiet
sudo -u auto-invest /usr/local/bin/uv sync --quiet

echo "[6/8] .env 생성 (chmod 0600, auto-invest 소유)"
umask 077
cat > /opt/auto-invest/.env <<EOF
KIS_APP_KEY=${KIS_APP_KEY}
KIS_APP_SECRET=${KIS_APP_SECRET}
KIS_ACCOUNT_NO=${KIS_ACCOUNT_NO}
AUTO_INVEST_CAPITAL=${AUTO_INVEST_CAPITAL}
AUTO_INVEST_MODE=dry-run
EOF
chown auto-invest:auto-invest /opt/auto-invest/.env
chmod 0600 /opt/auto-invest/.env
umask 022

echo "[7/8] SQLite 감사 로그 마이그레이션 적용"
cd /opt/auto-invest
sudo -u auto-invest /usr/local/bin/uv run auto-invest db migrate --db /opt/auto-invest/data/auto_invest.db

echo "[8/8] systemd 유닛 + 타이머 설치 + 활성화"
install -m 0644 /opt/auto-invest/deploy/auto-invest.service        /etc/systemd/system/auto-invest.service
install -m 0644 /opt/auto-invest/deploy/auto-invest-deploy.service /etc/systemd/system/auto-invest-deploy.service
install -m 0644 /opt/auto-invest/deploy/auto-invest-deploy.timer   /etc/systemd/system/auto-invest-deploy.timer
systemctl daemon-reload
systemctl enable --now auto-invest.service
systemctl enable --now auto-invest-deploy.timer

# 비밀 변수를 메모리/디스크에서 즉시 제거 (cloud-init log에 남지 않게).
unset KIS_APP_KEY KIS_APP_SECRET KIS_ACCOUNT_NO

echo
echo "========================================================"
echo "auto-invest 가동 완료 (dry-run 모드)"
echo
echo "확인:"
echo "  systemctl status auto-invest.service"
echo "  journalctl -u auto-invest.service -n 30"
echo "  sqlite3 /opt/auto-invest/data/auto_invest.db \\"
echo "    'SELECT ts_utc, event_type FROM audit_log ORDER BY seq DESC LIMIT 10;'"
echo
echo "1주일 후 실주문 전환 (한 줄):"
echo "  sed -i 's/^AUTO_INVEST_MODE=.*/AUTO_INVEST_MODE=live/' /opt/auto-invest/.env \\"
echo "  && systemctl restart auto-invest.service"
echo "========================================================"
