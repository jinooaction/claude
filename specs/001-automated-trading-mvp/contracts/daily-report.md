# Contract: Daily Report

Produced by `reports/daily.py` at end-of-session (US regular hours
close) and on demand via `auto-invest report`. Consumed by the operator
during the morning audit (SC-007: under five minutes to read).

## Storage

- File path: `data/reports/{session_date_YYYY-MM-DD}/daily-report.md`
- Plus a sibling `daily-report.json` carrying the same data in
  machine-readable form (so future tooling can diff or aggregate).
- Both files are immutable once written. A re-run with the same date
  reproduces byte-identical output unless the underlying audit log
  changed (in which case the report is regenerated and the previous
  file is renamed `daily-report.{generated_at}.md` for traceability).

## Content (Markdown)

```markdown
# auto-invest — Daily Report
Session date: 2026-05-02 (US regular hours)
Generated: 2026-05-03T04:31:12Z

## Summary
- Worker uptime during session:   100%
- Reconciliation result:          OK
- Halt flag:                      not set
- Orders attempted:               7
- Orders submitted to broker:     5
- Orders rejected by risk gates:  2
- Fills:                          5
- Realized P&L (estimate, USD):   +18.40
- End-of-day cash (USD):          $1,234.56
- Active rules:                   3

## Per-rule activity
| rule_id              | stage  | triggers | submitted | filled | rejected | reject_reasons       |
|----------------------|--------|---------:|----------:|-------:|---------:|----------------------|
| spy-morning-dip      | CANARY |        2 |         2 |      2 |        0 |                      |
| msft-ema-cross       | CANARY |        1 |         1 |      1 |        0 |                      |
| aapl-rsi-rebound     | CANARY |        4 |         2 |      2 |        2 | per_symbol_cap_gate  |

## Risk-gate rejections
1. ts=23:48:11Z rule=aapl-rsi-rebound symbol=AAPL gate=per_symbol_cap_gate
   limit=20.00% would_become=22.40%
2. ts=00:14:02Z rule=aapl-rsi-rebound symbol=AAPL gate=per_symbol_cap_gate
   limit=20.00% would_become=21.85%

## Positions (end of day)
| symbol | qty | avg_cost_usd | last_close_usd | unrealized_pnl_usd |
|--------|-----|--------------|----------------|--------------------|
| AAPL   |  10 |       182.50 |         184.21 |              17.10 |
| MSFT   |   3 |       418.40 |         421.10 |               8.10 |
| SPY    |  10 |       541.20 |         540.65 |              -5.50 |

## Reconciliation
- Internal positions vs broker:  match
- Internal cash vs broker:       match (within $0.02)

## Notable events
- 2026-05-02T13:31:00Z WORKER_STARTED
- 2026-05-02T20:00:00Z RECONCILIATION_OK
- 2026-05-02T20:00:01Z WORKER_STOPPED reason=session_close
```

## JSON schema (sibling file)

```json
{
  "session_date": "2026-05-02",
  "generated_at": "2026-05-03T04:31:12Z",
  "uptime_pct": 100.0,
  "reconciliation": "OK",
  "halt": null,
  "counters": {
    "orders_attempted": 7,
    "orders_submitted": 5,
    "orders_rejected_by_gate": 2,
    "fills": 5
  },
  "pnl_realized_usd": "18.40",
  "cash_usd": "1234.56",
  "rules": [
    {
      "rule_id": "spy-morning-dip",
      "stage": "CANARY",
      "triggers": 2,
      "submitted": 2,
      "filled": 2,
      "rejected": 0,
      "reject_reasons": []
    }
  ],
  "rejections": [
    {
      "ts_utc": "2026-05-02T23:48:11Z",
      "rule_id": "aapl-rsi-rebound",
      "symbol": "AAPL",
      "gate": "per_symbol_cap_gate",
      "limit_pct": "20.00",
      "would_become_pct": "22.40"
    }
  ],
  "positions": [
    {
      "symbol": "AAPL",
      "qty": 10,
      "avg_cost_usd": "182.50",
      "last_close_usd": "184.21",
      "unrealized_pnl_usd": "17.10"
    }
  ]
}
```

## Generation contract

- All numeric values are derived from the audit log; no live broker
  calls happen during report generation.
- Every section corresponds 1:1 to entities defined in
  `data-model.md`. If a section would be empty, it is rendered as
  `(none)` rather than omitted, so the diff between reports reflects
  reality rather than templating choices.
- The report MUST be available within five minutes of session close
  (SC-006); the implementation targets thirty seconds.
