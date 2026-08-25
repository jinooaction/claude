# Contract: Options Variance Risk Premium Evidence

## Probe Inputs

The command-line probe accepts:

- Cboe PUT daily history CSV;
- Cboe VIX daily history CSV;
- Kenneth French daily factor ZIP;
- FRED DGS3MO CSV;
- prior energy factory JSON carrying the 736-record audit catalog;
- released family decision JSON files for non-promoting adoption audit;
- code commit and evidence timestamp;
- JSON and Markdown output paths.

## Required JSON Surface

- `schema_version`, `timestamp_utc`, `code_commit`, `batch_id`
- `options_premium_data`, source hashes, chronology, and limitations
- `candidate_count=16`, `complete_trial_count=16`, `multiplicity_trial_count=16`
- `prior_trial_count=736`, `global_audit_trial_count=752`
- `unique_trial_fingerprint_count=752`
- `development_selection`, `holdout_confirmation`, `selection_sanity`
- `standalone_live_lane`, `standalone_paper_lane`, `timing_enhancement_lane`
- `reference_control`, including non-promoting premium-existence and portfolio-adoption diagnoses, `objective_gate_calibration`, `prior_adoption_audit`
- `decision`, `research_live_parity`, `trial_records`, `audit_records`, `safety`

## Publication Invariants

Publication MUST fail unless:

1. all four sources are complete, fresh, correctly identified, and source-hashed;
2. isolated pre-2007 PUT rows are excluded, at least 205 aligned months remain, and the 84/1/120-or-more split and all feature/model-label chronology checks pass;
3. 16 current records and 752 globally unique strategy fingerprints exist;
4. every gate result is a JSON boolean;
5. synthetic null false acceptance is at most 6% and planted detection at least 80%;
6. the frozen winner, split, strategy, target weights, sources, and model have `sha256:` fingerprints;
7. every prior-adoption row has `retroactive_promotion_allowed=false`;
8. broker imports, orders, capital, margin, whitelist, constitution, and kernel changes are absent.

## Verdict Contract

- `FACTORY_EDGE_CONFIRMED`: frozen winner passes standalone live gates.
- `PAPER_EDGE_CANDIDATE`: frozen winner fails live but passes standalone paper gates.
- `REFERENCE_EDGE_CONFIRMED_SELECTION_UNCONFIRMED`: full PUT reference passes but the frozen winner does not reach paper.
- `GATE_OR_REFERENCE_SUSPECT`: synthetic calibration is passable but the recognized reference fails unexpectedly, or controls are internally inconsistent.
- `NO_FACTORY_EDGE`: controls are coherent and neither frozen winner nor reference supports adoption.

All verdicts remain research-only until live parity is independently complete.
