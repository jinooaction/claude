#!/usr/bin/env bash
# Read-only production deploy audit query for the SSH forced-command gateway.
#
# The gateway accepts only `deploy-audit` or `deploy-audit <correlation_id>`.
# This helper validates the optional identifier again before using it in SQL.
# It never changes the database, worker, repository, configuration, or orders.

set -euo pipefail

PATH=/usr/sbin:/usr/bin:/sbin:/bin
DB_PATH="/opt/auto-invest/data/auto_invest.db"

if [[ "$#" -gt 1 ]]; then
    echo "AUDIT_STATUS=invalid_request"
    echo "Expected zero or one correlation_id argument." >&2
    exit 2
fi

cid="${1:-}"
if [[ -n "${cid}" && ! "${cid}" =~ ^[0-9a-fA-F]{8,64}$ ]]; then
    echo "AUDIT_STATUS=invalid_correlation_id"
    echo "correlation_id must be 8-64 hex characters." >&2
    exit 2
fi

if [[ ! -r "${DB_PATH}" ]]; then
    echo "AUDIT_STATUS=missing_db"
    echo "Database is not readable." >&2
    exit 3
fi

if [[ -z "${cid}" ]]; then
    if ! cid="$(sqlite3 -readonly "${DB_PATH}" \
        "SELECT correlation_id
           FROM audit_log
          WHERE event_type LIKE 'DEPLOY_%'
            AND correlation_id IS NOT NULL
            AND correlation_id != ''
          ORDER BY seq DESC
          LIMIT 1;")"; then
        echo "AUDIT_STATUS=query_failed"
        exit 5
    fi
fi

if [[ -z "${cid}" ]]; then
    echo "AUDIT_STATUS=no_deploy_rows"
    echo "No DEPLOY_* audit rows with correlation_id found."
    exit 4
fi

# A database-derived identifier is untrusted input too. Keep SQL interpolation
# limited to the same strict hex format enforced at the gateway and on argv.
if [[ ! "${cid}" =~ ^[0-9a-fA-F]{8,64}$ ]]; then
    echo "AUDIT_STATUS=invalid_db_correlation_id"
    echo "Latest deploy correlation_id has an invalid format." >&2
    exit 5
fi

if ! row_count="$(sqlite3 -readonly "${DB_PATH}" \
    "SELECT COUNT(*)
       FROM audit_log
      WHERE correlation_id = '${cid}'
        AND event_type LIKE 'DEPLOY_%';")"; then
    echo "AUDIT_STATUS=query_failed"
    exit 5
fi

if ! terminal_event="$(sqlite3 -readonly "${DB_PATH}" \
    "SELECT event_type
       FROM audit_log
      WHERE correlation_id = '${cid}'
        AND event_type LIKE 'DEPLOY_%'
      ORDER BY seq DESC
      LIMIT 1;")"; then
    echo "AUDIT_STATUS=query_failed"
    exit 5
fi

echo "AUDIT_STATUS=ok"
echo "AUDIT_CORRELATION_ID=${cid}"
echo "AUDIT_ROW_COUNT=${row_count}"
echo "AUDIT_TERMINAL_EVENT=${terminal_event}"
echo
echo "## DEPLOY audit rows"
sqlite3 -readonly -header -column "${DB_PATH}" \
    "SELECT seq,
            ts_utc,
            event_type,
            json_extract(payload_json, '$.phase') AS phase,
            substr(json_extract(payload_json, '$.sha_before'), 1, 12) AS sha_before,
            substr(json_extract(payload_json, '$.sha_after'), 1, 12) AS sha_after,
            json_extract(payload_json, '$.recovery_basis') AS recovery_basis,
            substr(json_extract(payload_json, '$.recovered_production_sha'), 1, 12) AS recovered_production,
            json_extract(payload_json, '$.reason') AS reason
       FROM audit_log
      WHERE correlation_id = '${cid}'
        AND event_type LIKE 'DEPLOY_%'
      ORDER BY seq;"
