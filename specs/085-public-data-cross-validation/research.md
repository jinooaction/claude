# Research: 공개 데이터 교차 검증 확장

## Decision: Add FRED graph CSV DGS2/DGS10 as keyless research-only series

**Rationale**: The latest candidate-result evidence for `candidate-facf2fa31834` shows `https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10` returned HTTP 200 quickly with the default HTTP client user-agent, while the channel user-agent path timed out. DGS2 and DGS10 are the same economic concepts as the existing Treasury UST2Y and UST10Y research inputs, so they are appropriate for level cross-checking.

**Alternatives considered**:

- Keep FRED probe-only: safest but misses a now-observed working keyless source.
- Use FRED official API: rejected because the endpoint requires an API key and this task must not add secrets.
- Add price history via Stooq: rejected because price source expansion remains out of scope and Stooq still shows a browser/JS barrier pattern.

## Decision: Use `httpx-default` user-agent only for configured FRED graph CSV series

**Rationale**: Existing public sources use a clear channel user-agent for honest identification. FRED graph CSV is the exception surfaced by live evidence: channel UA can tarpit, default UA can succeed. Making the user-agent mode explicit in config avoids changing all sources and keeps the exception auditable.

**Alternatives considered**:

- Remove channel UA globally: rejected because it changes behaviour for all sources and weakens diagnostic continuity.
- Retry FRED with both UAs: rejected for v1 because it adds request cost and ambiguity; a single explicit mode is easier to reason about.

## Decision: Add Treasury-vs-FRED level cross-checks with existing H.15 thresholds

**Rationale**: Existing Treasury-vs-DBnomics checks use 99.5% agreement and 0.001 tolerance to tolerate a small amount of timing/revision drift while still catching systematic unit, truncation, or transport problems. FRED DGS2/DGS10 should use the same posture.

**Alternatives considered**:

- Require 100% FRED agreement: rejected because long daily histories can legitimately have a few revision timing differences.
- Use returns-based checks: rejected because rate levels themselves are the economic signal and should be directly comparable.

## Decision: Preserve research-only isolation

**Rationale**: Public-data channel outputs are for research, backtest, and validation. Live trading signals continue to use KIS data only. The existing tests that forbid public-data consumption in trading workflows remain the enforcement surface.

**Alternatives considered**:

- Feed FRED rates into live strategy gates directly: rejected as outside scope and contrary to the research-only contract.
