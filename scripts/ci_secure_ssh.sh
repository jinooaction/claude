#!/usr/bin/env bash
# Shared GitHub Actions SSH hardening helper.

set -euo pipefail

ssh_user="${VULTR_SSH_USER:-${USER:-}}"
if [[ "$ssh_user" == "root" ]]; then
    echo "::error::VULTR_SSH_USER=root is refused. Use a restricted deploy user." >&2
    exit 2
fi

if [[ -z "${VULTR_SSH_PRIVATE_KEY:-${KEY:-}}" ]]; then
    echo "::error::missing VULTR_SSH_PRIVATE_KEY/KEY" >&2
    exit 2
fi
if [[ -z "${VULTR_SSH_KNOWN_HOSTS:-${KNOWN_HOSTS:-}}" ]]; then
    echo "::error::missing VULTR_SSH_KNOWN_HOSTS/KNOWN_HOSTS" >&2
    exit 2
fi

mkdir -p ~/.ssh
chmod 700 ~/.ssh
printf '%s\n' "${VULTR_SSH_PRIVATE_KEY:-${KEY:-}}" > ~/.ssh/id_ed25519
chmod 600 ~/.ssh/id_ed25519
printf '%s\n' "${VULTR_SSH_KNOWN_HOSTS:-${KNOWN_HOSTS:-}}" > ~/.ssh/known_hosts
chmod 600 ~/.ssh/known_hosts
