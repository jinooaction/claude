#!/usr/bin/env bash
# Shared GitHub Actions SSH hardening helper.

set -euo pipefail

ssh_user="${VULTR_SSH_USER:-${SSH_USER:-}}"
if [[ -z "${ssh_user}" ]]; then
    echo "::error::missing VULTR_SSH_USER/SSH_USER" >&2
    exit 2
fi
if [[ "$ssh_user" == "root" ]]; then
    echo "::error::VULTR_SSH_USER=root is refused. Use a restricted deploy user." >&2
    exit 2
fi

key="${VULTR_SSH_PRIVATE_KEY:-${KEY:-}}"
known_hosts="${VULTR_SSH_KNOWN_HOSTS:-${KNOWN_HOSTS:-}}"

if [[ -z "${key}" ]]; then
    echo "::error::missing VULTR_SSH_PRIVATE_KEY/KEY" >&2
    exit 2
fi
if [[ -z "${known_hosts}" ]]; then
    echo "::error::missing VULTR_SSH_KNOWN_HOSTS/KNOWN_HOSTS" >&2
    exit 2
fi

mkdir -p ~/.ssh
chmod 700 ~/.ssh
printf '%s\n' "${key}" > ~/.ssh/id_ed25519
chmod 600 ~/.ssh/id_ed25519
printf '%s\n' "${known_hosts}" > ~/.ssh/known_hosts
chmod 600 ~/.ssh/known_hosts
