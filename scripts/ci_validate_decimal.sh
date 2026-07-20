#!/usr/bin/env bash
# Validate a workflow_dispatch decimal before it is interpolated into a shell command.

set -euo pipefail

name="${1:?name required}"
value="${2:?value required}"

if [[ ! "$value" =~ ^[0-9]+([.][0-9]{1,2})?$ ]]; then
    echo "::error::${name} must be a positive decimal with up to two places." >&2
    exit 2
fi
