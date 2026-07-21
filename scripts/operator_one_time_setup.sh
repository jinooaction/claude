#!/usr/bin/env bash
# auto-invest — legacy operator setup guard.
#
# This script used to create a root SSH key and ask the operator to paste the
# private key into GitHub Actions secrets. That model is intentionally retired:
# GitHub-held root keys collapse the repository-to-server trust boundary.

set -euo pipefail

echo "============================================================"
echo "auto-invest — legacy root SSH setup retired"
echo "============================================================"
echo
echo "이 스크립트는 더 이상 root SSH 키를 만들거나 출력하지 않습니다."
echo "이유: GitHub Actions Secret 이 서버 root 개인키를 갖게 되면,"
echo "저장소/Actions 침해가 곧 서버 전체 권한과 실거래 경로로 이어질 수 있습니다."
echo
echo "새 운영 기준:"
echo "  - VULTR_SSH_USER 는 root 가 아니어야 합니다."
echo "  - VULTR_SSH_KNOWN_HOSTS 에 서버의 고정 SSH host key 를 등록해야 합니다."
echo "  - 서버에는 제한된 deploy 사용자와 root 소유 고정 명령 게이트를 별도 구성해야 합니다."
echo "  - 기존 GitHub용 root 키는 폐기하고 /root/.ssh/authorized_keys 에서 제거하세요."
echo
echo "대체 경로:"
echo "  fresh deploy 공개키를 만든 뒤 root 콘솔 또는 검증된 out-of-band SSH 에서"
echo "  deploy/repair-ssh-boundary.sh 를 DEPLOY_PUBLIC_KEY 와 함께 실행하세요."
echo "============================================================"
exit 2
