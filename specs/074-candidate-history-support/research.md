# Research: Candidate History Support

## Decision 1: Reuse existing bars-export and ingest-history

**Decision**: Build the support path from `bars-export` to `ingest-history` instead of adding a new price collector.

**Rationale**: `bars-export` is already a read-only bridge from stored server `price_bars` to the CSV contract consumed by `ingest-history`. Existing workflows use this chain for anchored verdict and regime stratification, so it has operational precedent.

**Alternatives considered**:

- Add broker backfill in candidate workflow: rejected because it would introduce broker/API and rate-limit concerns into candidate validation.
- Commit CSV history into the repo: rejected because generated market data should not become source.
- Let candidate commands SSH to the server: rejected because candidate package commands must remain local no-live commands.

## Decision 2: Centralize history mapping in a Python module

**Decision**: Add one manifest module for candidate history datasets and make factory, workflow probe, and tests consume it.

**Rationale**: Hardcoding roots independently in YAML and factory code would repeat the exact class of drift fixed by spec 073. One manifest gives a single review surface for portfolio path, DB path, and history root.

**Alternatives considered**:

- YAML-only mapping: rejected because candidate factory needs typed helper functions and tests.
- Inline workflow table: rejected because factory command generation would still need a separate copy.

## Decision 3: Keep workflow failures non-fatal

**Decision**: History staging is best-effort per dataset. Missing SSH secrets, missing DBs, zero bars, or ingest failures do not fail the whole workflow.

**Rationale**: The result executor already has machine-readable pending diagnostics. Failing the whole workflow would hide partial progress for non-strategy candidates and reduce observability.

**Alternatives considered**:

- Fail workflow when any history dataset is missing: rejected because it blocks unrelated candidates.
- Mark candidates passed when staging succeeds: rejected because real pass still requires `portfolio-walk-forward` output.

## Decision 4: Use current server DBs by candidate portfolio

**Decision**: Map current candidates as follows:

| key | portfolio | server DB | local history root |
|-----|-----------|-----------|--------------------|
| micro-gtaa | `deploy/micro-gtaa-live-portfolio.toml` | `data/auto_invest.db` | `/tmp/candidate_result_history/micro-gtaa/hist` |
| global-trend-wide | `deploy/global-trend-wide-portfolio.toml` | `data/forward_wide.db` | `/tmp/candidate_result_history/global-trend-wide/hist` |
| multi-asset-trend | `deploy/multi-asset-trend-portfolio.toml` | `data/forward_multiasset.db` | `/tmp/candidate_result_history/multi-asset-trend/hist` |

**Rationale**: These DBs are the same operational surfaces already used by current workflows or portfolio tracks. The support path reads them only.

**Alternatives considered**:

- Use one shared history root for all portfolios: rejected because source DB coverage differs and failures should be diagnosable per dataset.
- Use `data/history` in repo checkout: rejected because GitHub runners do not have persisted ingested datasets.
