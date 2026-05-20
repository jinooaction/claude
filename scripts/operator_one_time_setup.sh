#!/usr/bin/env bash
# auto-invest — 운영자 1회 셋업 자동화.
#
# 이 한 줄이 운영자 인스턴스 콘솔의 마지막 작업입니다.
# 그 후 모든 design 호출은 GitHub Actions UI 클릭 또는 cron schedule 로 자동.
#
# 사용법 (Vultr 콘솔 View Console, root 로그인):
#
#   curl -sSL https://raw.githubusercontent.com/jinooaction/claude/main/scripts/operator_one_time_setup.sh \
#     | sudo bash
#
# 또는 인스턴스에 이미 main 코드가 있으면:
#
#   sudo bash /opt/auto-invest/scripts/operator_one_time_setup.sh
#
# 이 스크립트가 자동 처리:
#
#   1. SSH 키페어 생성 (인스턴스 안에서 — 운영자 노트북에 키 보관 안 함, 더 안전)
#   2. 공개키를 root 의 authorized_keys 에 append
#   3. 화면에 GitHub Secrets 4개 값을 한글 안내와 함께 출력
#   4. 운영자가 출력 그대로 GitHub Settings 에 복붙
#
# 끝.

set -euo pipefail

if [[ "$(id -u)" -ne 0 ]]; then
    echo "ERROR: 이 스크립트는 sudo 또는 root 로 실행하세요." >&2
    exit 1
fi

KEY_NAME="${KEY_NAME:-auto_invest_gh}"
KEY_PATH="/root/.ssh/${KEY_NAME}"
PUB_PATH="${KEY_PATH}.pub"
AUTHORIZED_KEYS="/root/.ssh/authorized_keys"
INSTANCE_IP="${INSTANCE_IP:-}"

echo "============================================================"
echo "auto-invest — 운영자 1회 셋업 (마지막 콘솔 작업)"
echo "============================================================"

# IP 자동 감지 (Vultr 인스턴스는 보통 외부 IP 가 첫 번째 인터페이스).
if [[ -z "${INSTANCE_IP}" ]]; then
    INSTANCE_IP=$(ip -4 -o addr show scope global 2>/dev/null \
        | awk '{print $4}' | cut -d/ -f1 | head -n1 \
        || hostname -I 2>/dev/null | awk '{print $1}')
fi
if [[ -z "${INSTANCE_IP}" ]]; then
    echo "WARNING: 인스턴스 IP 자동 감지 실패. 아래 출력에서 IP 부분을 수동 입력하세요." >&2
    INSTANCE_IP="<직접 입력>"
fi
echo "  감지된 인스턴스 IP: ${INSTANCE_IP}"
echo

echo "[1/3] SSH 키페어 생성"
mkdir -p /root/.ssh
chmod 700 /root/.ssh
if [[ -f "${KEY_PATH}" ]]; then
    echo "  이미 존재하는 키 사용: ${KEY_PATH}"
else
    ssh-keygen -t ed25519 -f "${KEY_PATH}" -N "" -C "github-actions@auto-invest" >/dev/null
    echo "  새 키페어 생성: ${KEY_PATH}"
fi
chmod 600 "${KEY_PATH}"
chmod 644 "${PUB_PATH}"

echo
echo "[2/3] 공개키를 authorized_keys 에 등록"
touch "${AUTHORIZED_KEYS}"
chmod 600 "${AUTHORIZED_KEYS}"
pubkey=$(cat "${PUB_PATH}")
if grep -qxF "${pubkey}" "${AUTHORIZED_KEYS}"; then
    echo "  이미 등록됨 — skip."
else
    echo "${pubkey}" >> "${AUTHORIZED_KEYS}"
    echo "  공개키 등록 완료."
fi

echo
echo "[3/3] GitHub Secrets 4개 값 출력"
echo
echo "============================================================"
echo "다음 4개를 GitHub Settings 에 등록하세요."
echo
echo "  브라우저에서 다음 페이지 열기:"
echo "  https://github.com/jinooaction/claude/settings/secrets/actions"
echo
echo "  'New repository secret' 4번 클릭, 차례대로 다음 Name/Value 복붙:"
echo "============================================================"
echo
echo "--- Secret 1/4 ----------------------------------------------"
echo "  Name:  VULTR_SSH_HOST"
echo "  Value: ${INSTANCE_IP}"
echo
echo "--- Secret 2/4 ----------------------------------------------"
echo "  Name:  VULTR_SSH_USER"
echo "  Value: root"
echo
echo "--- Secret 3/4 ----------------------------------------------"
echo "  Name:  VULTR_SSH_PORT"
echo "  Value: 22"
echo
echo "--- Secret 4/4 ----------------------------------------------"
echo "  Name:  VULTR_SSH_PRIVATE_KEY"
echo "  Value: (아래 BEGIN..END 모든 줄 통째로 복사 — 한 줄도 빠지면 안 됨)"
echo
echo "----- 여기부터 복사 -----"
cat "${KEY_PATH}"
echo "----- 여기까지 복사 -----"
echo
echo "============================================================"
echo "셋업 끝. 4개 등록하시면 그 후로 영구 자율 수행:"
echo
echo "  방법 A — 직접 트리거 (UI 1 클릭):"
echo "    https://github.com/jinooaction/claude/actions/workflows/operator-design.yml"
echo "    → 'Run workflow' → intent 입력 → 'Run workflow' 클릭"
echo
echo "  방법 B — 자동 트리거 (운영자 클릭 0):"
echo "    workflow 파일이 cron schedule 로 매주/매일 자동 실행."
echo "    docs/OPERATOR_GITHUB_ACTIONS_DESIGN.md 의 'schedule' 섹션 참조."
echo
echo "  방법 C — 이슈 코멘트 트리거 (운영자가 한 줄만):"
echo "    GitHub Issue 에 코멘트로 'design: <의도>' 적으면 자동 실행."
echo "    (workflow 가 issue_comment trigger 도 받게 확장 가능 — 별도 PR.)"
echo
echo "이 콘솔 창은 이제 닫으셔도 됩니다. 위 4개 등록만 5분이면 끝."
echo "============================================================"
