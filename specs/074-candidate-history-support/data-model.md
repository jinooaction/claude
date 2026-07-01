# Data Model: Candidate History Support

## CandidateHistoryDataset

Deterministic support dataset for one current candidate portfolio.

| Field | Type | Description |
|------|------|-------------|
| `key` | string | Stable short key used in logs and directory names |
| `portfolio_path` | path | Repository portfolio TOML consumed by `portfolio-walk-forward` |
| `db_path` | path | Server SQLite DB read by `bars-export` |
| `history_root` | path | Runner-local parent directory passed to `--history-root` |

## CandidateHistoryManifest

Ordered collection of `CandidateHistoryDataset` rows.

| Field | Type | Description |
|------|------|-------------|
| `datasets` | list | Current required strategy/portfolio history datasets |
| `format` | enum | JSON for tests, TSV for shell workflow |
| `version` | string | Implicit code version from repository commit |

## CandidateBacktestCommand

Generated no-live validation command for candidate result execution.

| Field | Type | Description |
|------|------|-------------|
| `package_kind` | string | `strategy_backtest` or `portfolio_backtest` |
| `portfolio_path` | path | Portfolio TOML |
| `history_root` | path | Must match manifest row for the portfolio |
| `db_path` | path | Candidate audit DB path on the runner, not the server price DB |
| `halt_path` | path | Candidate-local halt flag path |

## Relationships

- Candidate factory looks up `CandidateHistoryDataset` by `portfolio_path`.
- Workflow reads `CandidateHistoryManifest` and prepares each dataset.
- Result executor consumes `CandidateBacktestCommand`; it does not know or use SSH.
- Promotion loop consumes result evidence only after result executor classifies pass/fail/pending.
