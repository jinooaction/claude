#!/usr/bin/env bash
# Vultr cloud-init User-Data — auto-invest 인스턴스 부팅 시 한 번에 실행.
#
# 사용법:
#   (A) 운영자가 Vultr 콘솔에서 인스턴스를 직접 만드는 경우:
#       이 파일 전체를 "User Data" / "Cloud-Init" 필드에 붙여넣고,
#       아래 CONFIGURE_ME에서 AUTO_INVEST_CAPITAL만 채우세요.
#       KIS 키는 인스턴스 부팅 후 콘솔에서 한 번 실행할 명령으로 박습니다:
#         bash /opt/auto-invest/scripts/set_secrets.sh
#
#   (B) API 토큰 위임으로 자동 생성하는 경우:
#       동일. 운영자는 인스턴스 생성된 후 Vultr 콘솔에서 위 한 줄 실행.
#
# 1주일 dry-run 관찰 후 실주문 전환:
#   sed -i 's/^AUTO_INVEST_MODE=.*/AUTO_INVEST_MODE=live/' /opt/auto-invest/.env \
#   && systemctl restart auto-invest.service
#
# 안전:
#   - 이 스크립트는 cloud-init이 root로 한 번만 실행합니다.
#   - KIS 키는 set_secrets.sh로 입력될 때까지 placeholder 상태이며,
#     워커는 placeholder 상태에서는 fail-safe로 가동되지 않습니다.
#   - 모든 로그는 /var/log/auto-invest-cloud-init.log에 남고, 비밀은 절대
#     echo하지 않습니다.

set -euo pipefail
exec > >(tee /var/log/auto-invest-cloud-init.log) 2>&1

# ============================================================================
# CONFIGURE_ME — 이 줄만 필요하면 바꾸세요. KIS 키는 부팅 후 set_secrets.sh로.
# ============================================================================
AUTO_INVEST_CAPITAL="100"
# ============================================================================

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

echo "[6/8] .env 생성 (chmod 0600, auto-invest 소유, KIS 키는 placeholder)"
umask 077
cat > /opt/auto-invest/.env <<EOF
# KIS 자격증명은 운영자가 다음 명령으로 박습니다:
#   bash /opt/auto-invest/scripts/set_secrets.sh
KIS_APP_KEY=
KIS_APP_SECRET=
KIS_ACCOUNT_NO=
AUTO_INVEST_CAPITAL=${AUTO_INVEST_CAPITAL}
AUTO_INVEST_MODE=dry-run
EOF
chown auto-invest:auto-invest /opt/auto-invest/.env
chmod 0600 /opt/auto-invest/.env
umask 022

echo "[7/8] SQLite 감사 로그 마이그레이션 적용"
cd /opt/auto-invest
sudo -u auto-invest /usr/local/bin/uv run auto-invest db migrate --db /opt/auto-invest/data/auto_invest.db

echo "[8/8] systemd 유닛 + 타이머 설치 (워커는 KIS 키 설정 전까지 fail-safe)"
install -m 0644 /opt/auto-invest/deploy/auto-invest.service        /etc/systemd/system/auto-invest.service
install -m 0644 /opt/auto-invest/deploy/auto-invest-deploy.service /etc/systemd/system/auto-invest-deploy.service
install -m 0644 /opt/auto-invest/deploy/auto-invest-deploy.timer   /etc/systemd/system/auto-invest-deploy.timer
systemctl daemon-reload
# 배포 타이머는 바로 활성화 (KIS 키와 무관하게 git pull 가능).
systemctl enable --now auto-invest-deploy.timer
# 워커는 enable만 하고 start는 운영자가 set_secrets.sh로 KIS 키 박은 다음에
# 자동으로 시작됩니다 (set_secrets.sh가 systemctl restart 호출).
systemctl enable auto-invest.service

echo
echo "========================================================"
echo "auto-invest 인스턴스 셋업 완료."
echo
echo "다음 한 줄을 이 콘솔에서 실행하셔서 KIS 자격증명을 박으세요."
echo "(입력값은 화면에 안 보이고, 로그/journal에도 절대 남지 않습니다)"
echo
echo "    bash /opt/auto-invest/scripts/set_secrets.sh"
echo
echo "그 명령이 KIS 키 3개를 prompt로 받고, .env에 저장하고, 워커를"
echo "dry-run 모드로 자동 가동합니다."
echo
echo "1주일 후 실주문 전환 (한 줄):"
echo "  sed -i 's/^AUTO_INVEST_MODE=.*/AUTO_INVEST_MODE=live/' /opt/auto-invest/.env \\"
echo "  && systemctl restart auto-invest.service"
echo "========================================================"
