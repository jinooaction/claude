# Server issuer observation contract

- A dedicated service invokes only the fixed Microsoft issuer collector. It
  has no `.env`/KIS environment file, brokerage client, portfolio, order, or
  account argument. The store path is fixed under
  `/var/lib/auto-invest-issuer-observations/store`. Its run ID is exactly
  `server-` plus the 32 lowercase hexadecimal characters of systemd's
  invocation ID; GitHub `actions-` runs are refused in server status and backup.
- Every actual listing GET yields a new receipt with its actual request,
  reception, and verification times. A planned timer slot is never an
  observation. Failed requests yield explicit failures, not empty coverage.
- `selection.unchanged` counts selected primary documents not fetched because
  the listing bytes matched a previously verified listing, the selected set
  was fully verified in that run, and that run finished less than 24 hours
  before the current run. It is distinct from `unselected` and
  `limit_skipped`. Legacy two-field manifests remain valid.
- A changed listing, prior failure, incomplete selected set, or expired
  validation forces the bounded primary GETs. The collector may not copy old
  receipts and assign a new observation time.
- Read-only status reports actual last attempt, completion, failures, missing
  scheduled slots, and separate remote backup freshness. Missing store or
  corrupted chain is an error, never a healthy empty state.
- Off-server backup uses a separate branch and checks every existing file
  digest before append-only publication. Existing issuer GitHub observations
  and server observations have distinct chain identities.
