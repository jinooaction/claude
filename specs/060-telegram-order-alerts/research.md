# Research: Telegram Order Alerts

## Decision: Use Telegram Bot API HTTPS directly, no new Python dependency

**Rationale**: Telegram's Bot API is a simple HTTPS interface and the repo already depends on `httpx`. Direct calls keep the supply chain unchanged and allow bounded timeout/retry logic in a small module.

**Alternatives considered**:

- `python-telegram-bot`: convenient but adds a large new dependency for a single `sendMessage` call.
- Discord webhook: easy, but the operator asked for Telegram and Telegram mobile notifications are direct.
- Pushover: reliable, but it introduces a paid/user-license assumption while Telegram's developer API is free of charge per Telegram's API page.

## Decision: Make audit-log alerts a separate tailer service

**Rationale**: Order routing and audit append must never wait on Telegram. A tailer that reads committed audit rows is naturally best-effort and can be enabled/disabled independently.

**Alternatives considered**:

- Send inside `OrderRouter`: closer to the event but risks blocking live orders or adding failure coupling.
- Send inside `audit.append`: would touch every audit producer and make persistence depend on an external API.
- GitHub-only notifications: covers scheduled workflows but cannot observe the continuous worker's live order/fill events.

## Decision: Default first run to current max seq

**Rationale**: Enabling mobile alerts on an existing live DB should not blast historical order events. Operators can explicitly replay existing rows for testing.

**Alternatives considered**:

- Replay all history by default: dangerous noise and potentially confusing stale alerts.
- Require a manual cursor always: too easy to misconfigure.

## Decision: Plain text messages with explicit truncation

**Rationale**: Plain text avoids Markdown escaping bugs and reduces the risk of formatting-sensitive secret leakage. Messages are capped below Telegram's text limit.

**Alternatives considered**:

- Markdown or HTML formatting: nicer display, but escaping mistakes are not worth it for order alerts.
- Sending raw JSON: complete but too hard to read on mobile and increases accidental data exposure.
