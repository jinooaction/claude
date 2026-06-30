# Research: Candidate Pending Next Actions

## Decision 1: Fix command contracts in candidate factory

**Decision**: Generate commands that match the current CLI and script contracts:

- `pipeline_liveness_probe.py --sidecar-dir /tmp/candidate_result_sidecars --strict --json`
- `auto-invest macro-regime --data-dir /tmp/candidate_result_public_data --json`

**Rationale**: Current result evidence shows command contract errors caused by missing `--sidecar-dir` and unsupported `--format json`. These are deterministic automation bugs, not strategy failures.

**Alternatives considered**:

- Change the probes to accept old arguments: rejected because it preserves stale contracts and hides the source of truth.
- Treat contract errors as permanent blocked: rejected because they are safe to auto-repair.

## Decision 2: Use pipeline liveness as current data quality validation

**Decision**: Replace the data quality candidate's default `bars-status` command with pipeline liveness sidecar validation.

**Rationale**: The current data quality candidate is about stale evidence and unsuccessful proof paths. Running `bars-status` without a prepared DB fails on `data/auto_invest.db` and does not test the candidate's stated evidence path. Pipeline liveness validates current sidecar freshness with no broker or order surface.

**Alternatives considered**:

- Create an empty local DB: rejected because it could produce meaningless pass evidence.
- Add a new market data ingest step here: rejected because price source selection and replay semantics require separate design.

## Decision 3: Stage support inputs in workflow

**Decision**: The result executor workflow collects pipeline liveness sidecars and public data snapshots before candidate execution.

**Rationale**: Candidate commands should use deterministic read-only paths. Without staging, valid commands still fail on missing local inputs in GitHub Actions.

**Alternatives considered**:

- Make each candidate command fetch its own sidecars: rejected because it spreads Git plumbing across candidate commands and weakens auditability.
- Commit sidecar copies into the repository: rejected because sidecars are generated state, not source.

## Decision 4: Leave price history missing as pending

**Decision**: Do not convert strategy/portfolio missing history into pass, and do not add an ad hoc data source in this feature.

**Rationale**: Backtest evidence must be reproducible and sourced. Public macro sidecars do not contain ETF price histories, and no safe price-history ingestion contract is present in this feature.

**Alternatives considered**:

- Use recent public data as a proxy for backtest history: rejected because it would weaken promotion evidence.
- Mark the strategy candidates blocked: rejected because the action is retryable once a safe history dataset exists.
