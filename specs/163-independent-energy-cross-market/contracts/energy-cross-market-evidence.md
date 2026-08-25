# Contract: Energy Cross-Market Strategy Evidence

The production JSON MUST contain:

- schema and gate versions, code commit, timestamp, batch ID;
- exactly 16 current trials, 720 prior trials, and 736 unique cumulative strategy fingerprints;
- four exact EIA source identities, URLs, units, hashes, coverage, age, and publication-lag declaration;
- French energy-return and FRED cash source hashes, coverage, and limitations;
- frozen policy grammar, deterministic model settings, model chronology proof, and model fingerprint;
- 120-month development window, one-month embargo, at least 180-month holdout, and split fingerprint;
- one development-selected candidate and no holdout reselection;
- standalone live and paper gates with actual values and thresholds;
- unchanged incumbent-diversifier gates as a separate diagnostic lane;
- empirical positive/null controls and synthetic false-acceptance/detection results;
- every candidate's development and holdout metrics;
- post-hoc best candidate and all pass snapshots with `promotion_allowed=false`;
- intended XLE expression and explicit missing implementation/whitelist/parity blockers;
- safety declaration: no broker, orders, capital, arming, caps, whitelist, constitution, or kernel change.

The canonical workflow MUST fail before sidecar replacement unless:

1. all four public sources and the long-history target are complete and fresh;
2. 16/16 candidates complete;
3. 736/736 cumulative fingerprints are unique;
4. every ridge prediction proves label chronology;
5. empirical positive control passes and null control fails;
6. every producer-declared blocking gate has a boolean result;
7. the selected candidate, target weights, split, sources, and model have SHA-256 fingerprints.

`FACTORY_EDGE` alone MUST NOT set `research_canary_eligible=true`. Missing exact live
implementation, whitelist authorization, hardened-canary evidence, deploy config, or
fingerprint identity keeps capital at rung 0.
