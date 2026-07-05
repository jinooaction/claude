# Research: Signal Diversification Edge Experiment

## Decision: Reuse forward sidecar as the signal evidence source

**Rationale**: The selected work packet explicitly names existing forward verdict and released-work as inputs. The forward sidecar already carries track keys, labels, universes, incumbent flag, observation counts, and verdict state, which are enough to classify the current signal search surface without adding external data.

**Alternatives considered**: Add a new market-data or factor exposure dependency. Rejected because this candidate is a no-live contract and should stay within existing sidecar evidence.

## Decision: Classify signal families from track metadata first

**Rationale**: Current track keys map cleanly to initial signal families: broad equity trend timing, risk-managed beta, multi-asset allocation, global diversification, fixed-weight allocation, and wide-universe allocation. This is deterministic, transparent, and testable from the forward sidecar.

**Alternatives considered**: Infer factor families from holdings or external classifications. Rejected for this slice because it would add data dependencies and make the first contract harder to reproduce.

## Decision: Treat universe overlap as the first low-overlap proxy

**Rationale**: The current sidecar exposes each track's universe. Comparing candidate universes with the incumbent `global` track gives a simple, deterministic first proxy for whether a candidate is genuinely different from the live-verification baseline.

**Alternatives considered**: Estimate return correlation or factor beta. Rejected for this slice because current sidecars do not expose enough comparable return history and observations are still below the forward threshold.

## Decision: Completion marker closes this candidate and lets autonomous-work advance

**Rationale**: This spec completes `candidate-signal-diversification-edge-experiment`, not the broader investment-edge frontier. Closing this candidate should let the existing investment-edge map advance to `candidate-cost-adjusted-edge-experiment`.

**Alternatives considered**: Modify autonomous-work selection logic. Rejected because current selection already orders investment edge templates by released status, so the completion marker is enough.
