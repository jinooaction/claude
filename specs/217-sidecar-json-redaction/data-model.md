# Data model
- Document: text plus zero or more code fences; output remains text.
- Fence: character (` or ~), opening length >=3, info label, body, closing length >= opening.
- JSON body: dict/list/scalar; sensitive dict values replaced by string marker.
- Non-sensitive numbers/bools/null retain their parsed values. No new status or timestamp.
- Public candidate identifier string: existing allowlist only.
- Invalid/unclosed body: plain-text redaction; no recovery or eligibility.
