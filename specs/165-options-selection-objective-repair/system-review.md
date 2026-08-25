# Expert Review: Automated Trading System

## Executive Conclusion

The system is substantially better at preventing a bad order than at proving a profitable
order. Automated order plumbing is credible, but no current strategy has enough independent,
executable evidence to justify live capital. There is no active P0 emergency because capital is
zero and real-order submission is disabled.

## Readiness Scores

| Area | Score | Current judgment |
|---|---:|---|
| Order automation | 8.0/10 | Signed scheduled path, one account authority, preflight, fill sync, and reconciliation exist; no accepted live strategy order has exercised the full chain. |
| Capital and risk safety | 8.5/10 | Deny-by-default whitelist/caps/halt gates, capital ladder, fingerprint matching, and immediate demotion are strong. |
| Data integrity | 6.0/10 | Official sources, schema/freshness checks, and hashes exist; research histories are not vintage snapshots. |
| Research and statistics | 5.0/10 | Holdouts, costs, PSR/DSR/PBO, controls, and now nested cross-index replay exist; program-wide selection multiplicity remains unresolved. |
| AI advantage | 4.0/10 | Ridge and gradient boosting challengers are real walk-forward experiments, but both current AI sidecars say `NO_EDGE` and neither controls live allocation. |
| Execution parity | 4.0/10 | Equity routing is implemented; benchmark/options research and small-capital portfolio targets are not exact executable replicas. |
| Profit-edge readiness | 2.0/10 | Current live candidate is `NO_EDGE`, forward capital evidence is 0/20, live strategy fills are 0, and spec 165 confirms no cross-index options edge. |

Overall live-profit readiness is **2.0/10**, capped by the weakest mandatory lane: validated
profit edge. More automation cannot raise this score until the research and execution evidence
agree on one executable strategy.

## Findings

### P1-01: No current investable edge is confirmed

- **Evidence**: `automation/money-path-last-run` reports `PREVIEW_ONLY`, rung 0, capital $0,
  forward 0/20, and no fills. `automation/edge-autoarm-last-run` reports `WAIT_EDGE`; the exact
  deployed candidate's anchored verdict is `NO_EDGE`. The ML ensemble and daily cross-asset ML
  sidecars both report `NO_EDGE`. The spec-165 production replay reports
  `NO_CROSS_INDEX_PREMIUM`.
- **Money-path effect**: Any real buy would be unsupported by current profit evidence.
- **Remediation**: Keep capital at zero. Promote only a strategy that passes independent data,
  executable-cost parity, program-wide multiplicity, and clean forward evidence under one exact
  fingerprint.
- **Status**: OPEN; correctly blocked by current gates.

### P1-02: The factory consumer trusts producer-declared research sufficiency

- **Evidence**: `factory_evidence.py` requires the producer's `FACTORY_EDGE`,
  `research_canary_eligible`, passing blocking gates, counts, and selected output. It does not
  independently require vintage data, program-wide multiplicity, or execution-parity fields.
  `capital_ladder.py` can place a factory-ready candidate directly into rung 1 at 10% NAV without
  clean forward evidence. Live-entry revalidation adds freshness, exact config fingerprint, and
  hardened canary, but still inherits the producer's research contract.
- **Money-path effect**: A future buggy factory can overstate its own evidence and reach 10% NAV.
- **Remediation**: Create `family-complete-v3`: the consumer must independently require
  point-in-time status, program-wide trial budget, executable instrument/cost parity, nested or
  untouched selection evidence, and explicit no-historical-reuse before factory entry.
- **Status**: OPEN latent risk; current options output fails closed and cannot trigger it.

### P1-03: The 752-trial catalog is unique, not program-wide multiplicity-corrected

- **Evidence**: The factory consumer verifies 752 global unique fingerprints, while each released
  family computes multiplicity on only its current 16 or 64 records. The research program then
  moves to another family after observing prior failures.
- **Money-path effect**: Family-by-family false-positive control understates the chance of finding
  one lucky winner across the whole program.
- **Remediation**: Maintain one research-program alpha budget and hierarchical family selection
  correction. Historical families already inspected must be marked reused and cannot promote.
- **Status**: OPEN. Spec 165 marks its results `historical_reuse=true` and non-promotable.

### P1-04: Options benchmark evidence has no executable live counterpart

- **Evidence**: PUT/WPUT are hypothetical Cboe benchmark indexes. The live whitelist contains
  only `SPYM`, `IEF`, and `GLDM`; the option factory explicitly lacks option-chain history,
  assignment, taxes, margin, collateral, and broker execution parity.
- **Money-path effect**: Even a passing index backtest would not be an orderable strategy.
- **Remediation**: Do not connect this family to capital. A future options project needs a broker
  and account that support the exact contracts, historical bid/ask and assignment simulation,
  collateral accounting, and a paper-to-live fingerprint.
- **Status**: OPEN; safely isolated from orders.

### P2-01: Public research histories are current snapshots, not vintage data

- **Evidence**: The options bundle records `point_in_time=false` and says the histories are
  source-hashed but not vintage archives.
- **Money-path effect**: Revision and availability timing can make a historical signal cleaner
  than information known at the time.
- **Remediation**: Archive each scheduled raw download with observed timestamp and publication
  lag; select only from files available before each decision date.
- **Status**: OPEN.

### P2-02: Small-capital execution cannot faithfully represent the validated portfolio

- **Evidence**: The live candidate targets three equal-weight legs, maps research ETFs to cheaper
  execution ETFs, rounds to whole shares, and suppresses trades below $50. Rung 1 is about $145
  at the current $1,454 NAV, so each theoretical leg is only about $48 before rounding.
- **Money-path effect**: Early live returns can be dominated by one or two affordable legs rather
  than the validated SPY/IEF/GLD portfolio.
- **Remediation**: Add a fundability gate that simulates exact quotes, whole shares, minimum
  notional, caps, and symbol mapping before arming; require realized target-weight error below a
  fixed limit.
- **Status**: OPEN. The current config discloses this, but capital promotion does not block on it.

### P2-03: Forward truth is fragmented across measurement epochs

- **Evidence**: The canonical money-path and edge-autoarm sidecars report 0 observations, while an
  older anchored-verdict sidecar reports 48 observations under another dataset/version and still
  says `NO_EDGE`.
- **Money-path effect**: The canonical gate is safe, but operators can misread old observations as
  current evidence.
- **Remediation**: Publish one canonical measurement-contract ID and reject or visibly quarantine
  every sidecar from a different epoch.
- **Status**: OPEN observability issue; no capital impact today.

### P3-01: Automation can select generic work instead of the diagnosed research defect

- **Evidence**: `autonomous-work-execution-last-run` selected a generic “parallel edge challenger”
  while the live handoff specifically named options selection/objective repair.
- **Money-path effect**: Engineering effort can expand search breadth without first repairing
  evidence quality.
- **Remediation**: Rank explicit handoff diagnoses and P1 review findings above generic candidate
  templates; require a strategy family, data source, and falsifiable completion gate.
- **Status**: OPEN. The operator's direct instruction correctly overrode it this session.

## Strong Controls Worth Keeping

- The live workflow defaults to preview, requires signed scheduled authorization, and uses manual
  dispatch only for no-order preflight.
- `OrderRouter` records intent before submission, holds a single account authority lock, and turns
  uncertain submissions into `SUBMISSION_UNKNOWN` instead of blind retries.
- Execution state blocks new buys while an unknown or stale submission exists, while preserving
  verified reduce-only exits.
- Post-trade fill sync and multi-market reconciliation are mandatory; inconclusive reconciliation
  degrades execution rather than assuming success.
- Exact strategy fingerprints, kill switch, K1 caps, K2 whitelist, append-only audit records, and
  capital-ladder demotion materially reduce loss from software or broker failures.

## Next Priority

Implement `family-complete-v3` consumer-side evidence hardening and the exact fundability gate in
one grade-4 specification. After that, add the research-program-wide multiplicity budget. New
strategy searches should wait until these two paths prevent another statistically attractive but
non-executable candidate from reaching capital.
