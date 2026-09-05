#!/usr/bin/env bash
# 승인 판단의 기준 main이 대기·검증 중 바뀌면 상태 변경 없이 종료한다.
set -euo pipefail
expected="${GITHUB_SHA:-}"
if [[ ! "${expected}" =~ ^[0-9a-f]{40}$ ]]; then
  echo "AUTOARM_BASE_BLOCKED: invalid event commit" >&2
  exit 75
fi
if ! remote_line="$(git ls-remote --exit-code origin refs/heads/main)"; then
  echo "AUTOARM_BASE_BLOCKED: cannot verify current main" >&2
  exit 75
fi
if [[ "${remote_line}" != "${expected}"$'\trefs/heads/main' ]]; then
  echo "AUTOARM_BASE_BLOCKED: event commit is no longer current main; no capital change" >&2
  exit 75
fi
