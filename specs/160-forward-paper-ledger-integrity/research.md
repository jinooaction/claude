# Research: Forward Paper Ledger Integrity

## Decision: Treat negative paper cash as invalid measurement, not a warning

**Rationale**: Production showed fixed $12,000 tracks with cash between roughly -$55,000 and -$151,000 and holdings between roughly $68,000 and $167,000. NAV remained algebraically equal to capital plus profit, but the profit came from gross exposure far above the declared unlevered strategy. PSR, Sharpe, and Calmar on that curve do not describe the deployable configuration.

**Alternatives considered**:

- Keep warning-only behavior: rejected because invalid evidence can reach the capital ladder.
- Reject any market value above initial capital: rejected because normal appreciation can exceed the initial capital without borrowing.
- Use a small tolerance around zero: selected. Values below -$0.01 indicate simulated borrowing; rounding at or above -$0.01 is tolerated.

## Decision: Start a versioned clean database epoch

**Rationale**: PR #566 stopped new repeated buys by reconstructing paper holdings, but old leveraged fills and snapshots remain in each active database. `hold_replace` intentionally does not trim an existing target, so some old overexposure cannot reliably self-clean. A new isolated database immediately prevents old fills and NAV points from entering the active statistical suffix while preserving all audit evidence.

**Alternatives considered**:

- Delete or truncate old rows: rejected because audit history is append-only.
- Rewrite old fills with corrective synthetic trades: rejected because it changes forensic meaning and still leaves contaminated returns.
- Add an epoch field inside the same audit log: viable but broader than a path epoch and easier to misuse across consumers.
- Versioned databases: selected because isolation is already the track boundary and every consumer can be contract-tested.

## Decision: Move every producer and consumer together

**Rationale**: Updating only the daily producer would leave ladder, candidate history, signal IC, and cross-asset consumers reading legacy paths. The observation helper is the production source of truth, while candidate support and ML defaults must match it.

**Alternatives considered**:

- Compatibility fallback to legacy DB when clean DB is empty: rejected because it silently reintroduces invalid evidence.
- Copy legacy price bars into the clean DB: rejected as an operational mutation; existing backfill safely repopulates bars without copying fills or NAV.

## Decision: Invalidate current strategy eligibility without invalidating historical holdout research

**Rationale**: The exact `globalfixed` historical holdout remains a separate, temporally split, cost-adjusted calculation. Only the current paper forward observation counts and PSR values depend on the corrupted ledgers. After deployment, clean forward evidence starts from insufficient data and capital remains at rung 0.
