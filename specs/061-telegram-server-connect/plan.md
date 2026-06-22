# Implementation Plan: Telegram Server Connection Workflow

**Branch**: `Codex/telegram-server-connect` | **Date**: 2026-06-22 | **Spec**: [spec.md](./spec.md)

## Summary

Add a manual GitHub Actions workflow that uses existing GitHub secrets to configure Telegram alerts on the server. The workflow writes Telegram values into `/opt/auto-invest/.env`, sends a test message through the already-shipped `auto-invest telegram-alerts` CLI, installs the observer service if needed, and enables only that observer service.

## Technical Context

**Language/Version**: GitHub Actions YAML, Bash, Python 3 on server  
**Primary Dependencies**: Existing SSH secrets, existing `auto-invest telegram-alerts` CLI  
**Storage**: Server `/opt/auto-invest/.env` and systemd service state  
**Testing**: Static workflow tests, full pytest, ruff  
**Constraints**: No order path changes, no token logging, no worker restart, no committed secrets

## Constitution Check

| Principle | Assessment |
|-----------|------------|
| I. Position Sizing & Exposure Limits | No sizing or order behavior changes. |
| II. Deny-by-Default | No whitelist or tradable universe changes. |
| III. Claude Judgment Points | No LLM calls. |
| IV. Append-Only Audit Log | No audit schema or row mutation. |
| V. Secret Isolation | Uses GitHub Secrets and writes server `.env`; masks values in logs. |
| VI. Staged Rollout | Observability service only, no strategy/capital promotion. |
| VII. External API Robustness | Uses previously bounded Telegram CLI test path. |
| VIII.A Change Discipline | No trading worker restart; only observer service enable. |
| IX. Self-Modification Boundary | No kernel/constitution changes. |
| X. Measurement-Driven Growth | Improves operator visibility without changing growth logic. |

## Project Structure

```text
.github/workflows/configure-telegram-alerts.yml
tests/unit/test_configure_telegram_alerts_workflow.py
specs/061-telegram-server-connect/
```

## Safety Decision

The workflow is intentionally manual (`workflow_dispatch`) and narrow. It configures only Telegram observer settings and starts only `auto-invest-telegram-alerts.service`. It does not call live order commands, `auto-invest deploy`, `go-live`, or trading worker restarts.
