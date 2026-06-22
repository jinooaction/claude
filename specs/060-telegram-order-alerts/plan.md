# Implementation Plan: Telegram Order Alerts

**Branch**: `Codex/telegram-order-alerts` | **Date**: 2026-06-22 | **Spec**: [spec.md](./spec.md)  
**Input**: Feature specification from `specs/060-telegram-order-alerts/spec.md`

## Summary

Add mobile Telegram visibility for real-money order activity without putting Telegram on the trading decision path. The implementation adds a best-effort micro GTAA workflow notification step, a server-side audit_log tailer CLI/service for live order events, secret masking, cursor persistence, dry-run/test-message modes, and operator setup docs.

## Technical Context

**Language/Version**: Python 3.11 plus GitHub Actions YAML and systemd units  
**Primary Dependencies**: Existing `httpx`, `python-dotenv`, `typer`, `pytest`, `ruff`; no new package dependency  
**Storage**: Existing SQLite `audit_log`; JSON state file under `data/telegram_alerts_state.json`; GitHub Actions secrets for workflow notification  
**Testing**: `pytest`, `ruff`, existing workflow-static tests  
**Target Platform**: GitHub Actions runner and Linux Vultr host running systemd  
**Project Type**: Python CLI + read-only observability daemon + guarded workflow notification  
**Performance Goals**: Audit tail poll loop should send new alerts within one poll interval; one send attempt must use bounded timeout and retries  
**Constraints**: No order submission changes; no order-path dependency on Telegram; no committed secrets; alerts must be best-effort and non-blocking  
**Scale/Scope**: One operator chat, low-volume live/canary order events, text-only alerts

## Constitution Check

| Principle | Assessment |
|-----------|------------|
| I. Position Sizing & Exposure Limits | No sizing or exposure code changes. Alerts observe audit rows after decisions. |
| II. Deny-by-Default | No whitelist, account, order type, or session expansion. |
| III. Claude Is Invoked Only at Defined Judgment Points | No LLM calls. |
| IV. Append-Only Audit Log + Daily Reconciliation | Reads audit_log only; does not mutate prior rows. |
| V. Secret Isolation | Adds Telegram token/chat id runtime secrets and masks outbound alert content. No secrets committed. |
| VI. Staged Rollout | Observability only; no strategy/capital promotion. |
| VII. External API Robustness | Telegram sends use bounded timeout and retry; failures do not cascade to trading. |
| VIII.A Change Discipline | Merges through PR. New service is installed but not auto-enabled by deploy sync. |
| IX. Self-Modification Boundary | No kernel manifest change. Secret/external API handling makes this risk grade 3, but safety perimeter values remain unchanged. |
| X. Measurement-Driven Autonomous Growth | Improves operator visibility into live evidence; does not tune or scale capital. |

## Project Structure

### Documentation (this feature)

```text
specs/060-telegram-order-alerts/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── telegram-order-alerts.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

### Source Code (repository root)

```text
src/auto_invest/
├── notifications/
│   ├── __init__.py
│   ├── audit_tail.py
│   └── telegram.py
└── cli.py

tests/
├── integration/
│   └── test_telegram_alerts_cli.py
└── unit/
    ├── test_telegram_alerts.py
    └── test_micro_gtaa_telegram_alerts.py

.github/workflows/
└── rebalance-micro-gtaa-canary.yml

deploy/
├── auto-invest-telegram-alerts.service
├── sync-units.sh
└── README.md
```

**Structure Decision**: Use a separate observer/tailer instead of adding network sends inside `OrderRouter` or `audit.append`. This keeps Telegram failures outside the trading decision and persistence path.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| New external API call site | Mobile push alerts require a messaging service. | Polling GitHub manually is not real-time enough for order execution visibility. |
| New runtime secrets | Telegram Bot API requires bot token and chat id. | Hardcoding or committing credentials would violate secret isolation. |
| New optional systemd service | General worker order events happen on the server, not in GitHub Actions. | GitHub-only notifications cannot observe continuous worker `audit_log` events. |

## Phase 0 Research

See [research.md](./research.md).

## Phase 1 Design

See [data-model.md](./data-model.md), [contracts/telegram-order-alerts.md](./contracts/telegram-order-alerts.md), and [quickstart.md](./quickstart.md).

## Post-Design Constitution Check

The design remains outside the trading safety perimeter. It adds a new observer process and external notification API but leaves position sizing, whitelist, order routing, live capital, strategy selection, audit schema, and broker submission behavior unchanged. Telegram failures are bounded and do not fail the order path.
