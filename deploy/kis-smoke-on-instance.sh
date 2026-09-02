#!/usr/bin/env bash
# Run the KIS live-read smoke test on the operator instance through the
# fixed deploy gateway. This script is installed root-owned by
# repair-ssh-boundary.sh and is intentionally narrow: it reads KIS credentials
# from /opt/auto-invest/.env, checks out the target commit into /tmp, and runs
# the read-only integration smoke tests there.

set -uo pipefail

LIVE_REPO="${LIVE_REPO:-/opt/auto-invest}"
TARGET_SHA="${1:-${TARGET_SHA:-origin/main}}"
FALLBACK_REMOTE_URL="${FALLBACK_REMOTE_URL:-https://github.com/jinooaction/claude.git}"

if [[ "$(id -u)" -ne 0 ]]; then
    echo "::warning::kis-smoke helper must run as root via the deploy gateway (setup pending)."
    exit 100
fi
if [[ "${TARGET_SHA}" != "origin/main" && ! "${TARGET_SHA}" =~ ^[0-9a-f]{40}$ ]]; then
    echo "::warning::unsafe TARGET_SHA '${TARGET_SHA}' — expected origin/main or a 40-char commit SHA."
    exit 100
fi
if [[ ! -d "${LIVE_REPO}" ]]; then
    echo "::warning::${LIVE_REPO} 가 인스턴스에 없습니다 — provision-vultr.yml 미실행 (셋업 보류)."
    exit 100
fi

echo "--- smoke 전용 checkout 준비 ---"
echo "운영 repo: ${LIVE_REPO} (읽기 전용: .env/remote URL 확인만)"
echo "대상 commit: ${TARGET_SHA}"

# smoke 는 운영 워커가 쓰는 /opt/auto-invest 작업트리를 절대 checkout/reset 하지 않는다.
# 배포 상태기계만 운영 repo 를 갱신해야 deploy no-op/worker 미재시작 경쟁이 사라진다.
git config --global --add safe.directory "${LIVE_REPO}" 2>/dev/null || true
sudo -u auto-invest git config --global --add safe.directory "${LIVE_REPO}" 2>/dev/null || true
remote_url="$(git -C "${LIVE_REPO}" config --get remote.origin.url 2>/dev/null || true)"
remote_url="${remote_url:-${FALLBACK_REMOTE_URL}}"

smoke_parent=/tmp/auto-invest-kis-smoke
mkdir -p "${smoke_parent}"
chmod 1777 "${smoke_parent}" 2>/dev/null || true
SMOKE_REPO="$(sudo -u auto-invest mktemp -d "${smoke_parent}/repo.XXXXXX" 2>/dev/null || mktemp -d "${smoke_parent}/repo.XXXXXX")"
trap 'sudo rm -rf "${SMOKE_REPO:-}" 2>/dev/null || rm -rf "${SMOKE_REPO:-}"' EXIT

if ! sudo -u auto-invest git clone --quiet --no-checkout "${remote_url}" "${SMOKE_REPO}" 2>/dev/null; then
    rm -rf "${SMOKE_REPO:?}/"* "${SMOKE_REPO}/".[^.]* 2>/dev/null || true
    clone_url="${FALLBACK_REMOTE_URL}"
    sudo -u auto-invest git clone --quiet --no-checkout "${clone_url}" "${SMOKE_REPO}" 2>/dev/null || git clone --quiet --no-checkout "${clone_url}" "${SMOKE_REPO}"
    chown -R auto-invest:auto-invest "${SMOKE_REPO}" 2>/dev/null || true
fi
git config --global --add safe.directory "${SMOKE_REPO}" 2>/dev/null || true
sudo -u auto-invest git config --global --add safe.directory "${SMOKE_REPO}" 2>/dev/null || true
sudo -u auto-invest git -C "${SMOKE_REPO}" fetch --quiet origin main
if [[ "${TARGET_SHA}" != "origin/main" ]]; then
    if ! sudo -u auto-invest git -C "${SMOKE_REPO}" merge-base --is-ancestor "${TARGET_SHA}" origin/main; then
        echo "::warning::target commit ${TARGET_SHA} is not reachable from origin/main (setup pending)."
        exit 100
    fi
fi
sudo -u auto-invest git -C "${SMOKE_REPO}" checkout --quiet --detach "${TARGET_SHA}"
echo "smoke HEAD: $(git -C "${SMOKE_REPO}" rev-parse --short HEAD) ($(git -C "${SMOKE_REPO}" log -1 --pretty=%s))"
echo
echo "--- .env 확인 (KIS 키만 ✓ 표시, 값 노출 안 함) ---"
if [[ ! -f "${LIVE_REPO}/.env" ]]; then
    echo "::warning::${LIVE_REPO}/.env 파일이 없습니다 — scripts/set_secrets.sh 미실행 (셋업 보류)."
    exit 100
fi
missing_env=()
for k in KIS_APP_KEY KIS_APP_SECRET KIS_ACCOUNT_NO; do
    if grep -qE "^${k}=[^[:space:]]" "${LIVE_REPO}/.env"; then
        echo "  ${k}: ✓ 설정됨"
    else
        missing_env+=("${k}")
    fi
done
if [[ ${#missing_env[@]} -gt 0 ]]; then
    echo "::warning::.env 에 다음 KIS 키 누락: ${missing_env[*]} (셋업 보류)."
    exit 100
fi
echo
echo "--- KIS_LIVE_TEST=1 라이브 smoke 실행 ---"
read_env_value() {
    local key="$1"
    local line value
    line="$(grep -E "^${key}=" "${LIVE_REPO}/.env" | tail -1 || true)"
    value="${line#*=}"
    value="${value%$'\r'}"
    value="${value#"${value%%[![:space:]]*}"}"
    value="${value%"${value##*[![:space:]]}"}"
    if [[ "${value}" == \"*\" && "${value}" == *\" ]]; then
        value="${value:1:${#value}-2}"
    elif [[ "${value}" == \'*\' && "${value}" == *\' ]]; then
        value="${value:1:${#value}-2}"
    fi
    printf '%s' "$value"
}
KIS_APP_KEY="$(read_env_value KIS_APP_KEY)"
KIS_APP_SECRET="$(read_env_value KIS_APP_SECRET)"
KIS_ACCOUNT_NO="$(read_env_value KIS_ACCOUNT_NO)"

# sudo -E 가 root 의 HOME=/root 로 남으면서 auto-invest 가 root 의
# ~/.cache/uv 에 접근 시도 → permission denied. UV_CACHE_DIR / HOME 을 명시
# 전달한다. Pytest cache는 서버의 이전 root-owned 흔적을 피하려고 끈다.
AUTO_INVEST_HOME=$(getent passwd auto-invest 2>/dev/null | cut -d: -f6 || echo /tmp)
cd "${SMOKE_REPO}"
KIS_LIVE_TEST=1 sudo -E -u auto-invest \
    env "PATH=$PATH" \
        "HOME=${AUTO_INVEST_HOME}" \
        "UV_CACHE_DIR=${AUTO_INVEST_HOME}/.cache/uv" \
        "KIS_LIVE_TEST=1" \
        "KIS_APP_KEY=$KIS_APP_KEY" \
        "KIS_APP_SECRET=$KIS_APP_SECRET" \
        "KIS_ACCOUNT_NO=$KIS_ACCOUNT_NO" \
        "KIS_TOKEN_CACHE_PATH=${LIVE_REPO}/data/kis_token.json" \
    /usr/local/bin/uv run --project "${SMOKE_REPO}" pytest \
        tests/integration/test_live_broker.py -v -s \
        -p no:cacheprovider 2>&1
pytest_exit=$?
if [[ "${pytest_exit}" -ne 0 ]]; then
    echo "::warning::KIS smoke failed after one token issue; not retrying full live tests to avoid KIS OAuth throttle and duplicate live-read noise."
fi
exit "${pytest_exit}"
