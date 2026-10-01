#!/usr/bin/env bash
# Fixed public-source command: no account environment and no caller-controlled URL/path.
set -euo pipefail

[[ "${INVOCATION_ID:-}" =~ ^[0-9a-f]{32}$ ]] || {
    echo "missing systemd invocation identity" >&2
    exit 2
}

readonly PYTHON=/opt/auto-invest/.venv/bin/python
readonly ROOT=/opt/auto-invest
readonly STORE=/var/lib/auto-invest-issuer-observations/store
cd "$ROOT"

"$PYTHON" scripts/filing_publication.py --mode capacity --source "$STORE"
exec "$PYTHON" scripts/filing_observations.py collect-issuer-server \
    --config deploy/issuer-filings.json \
    --store "$STORE" \
    --run-id "server-${INVOCATION_ID}"
