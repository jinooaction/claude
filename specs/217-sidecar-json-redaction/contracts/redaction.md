# Public report redaction contract
CLI is unchanged: `python scripts/redact_public_sidecar.py [path ...]`; no path reads stdin.
Existing recursive directory selection and .git exclusion remain.
Valid JSON code fences use the same recursive policy as JSON files. Normal prose and other code use existing patterns.
Opening: 0–3 spaces, >=3 identical backticks or tildes, json label ignoring case and surrounding whitespace.
Closing: same character, >= opening length, whitespace only. Inner fences in another code language do not open JSON.
Malformed and unclosed blocks follow existing text policy; no fabricated values or success state.
The output is idempotent. Errors must not add raw input content to new diagnostics.
Existing producers/consumers and live gate configuration are unchanged.
