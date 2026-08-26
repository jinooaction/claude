# Research: Calibrated Research Entry

## Decision 1: Separate within-family selection from program-level research spending

DSR and PBO were designed to diagnose selection over many tried configurations. Applying both as
hard thresholds and then applying Bonferroni to every raw configuration counts much of the same
selection risk repeatedly. The ledger therefore records raw candidates for audit but spends the
program error budget by preregistered research family.

- Bailey et al., *The Probability of Backtest Overfitting*: https://escholarship.org/uc/item/4w1110bb
- Bailey and Lopez de Prado, *The Deflated Sharpe Ratio*: https://papers.ssrn.com/sol3/Delivery.cfm/SSRN_ID2460551_code87814.pdf?abstractid=2460551
- Harvey, Liu, and Zhu, *... and the Cross-Section of Expected Returns*: https://www.nber.org/papers/w20592
- Hansen, *A Test for Superior Predictive Ability*: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=264569

## Decision 2: Frozen threshold is PSR 0.95 and PBO 0.25

Using seed 60,000, 500 repetitions, 80% candidate correlation, 204 development observations, 235
holdout observations, and a planted annual Sharpe of 0.60 produced the preregistration evidence:

| Family size | Null acceptance | Planted-edge detection |
|---:|---:|---:|
| 16 | 0.010 | 0.840 |
| 64 | 0.004 | 0.804 |

The same framework showed the existing simultaneous hard gates had planted-edge detection near
0.42 for 16 candidates and 0.36 for 64 candidates. The new threshold is frozen before modifying
the consumer and is not selected from the current options result.

## Decision 3: Program budget is 20 families at a 1% family ceiling

The current ledger has 17 actual research families and 752 raw candidates. A union-bound budget
does not assume the families are independent: `17 * 0.01 = 0.17 <= 0.20`. The 21st family blocks
without a new preregistered calibration. This is a research false-admission budget, not a claim
that the accepted strategy has a 20% chance of loss.

## Decision 4: Current options family remains rejected

The repaired 16x8 segment matrix produces PBO 0.371429, above the new 0.25 maximum. It also has no
selected promotion candidate and fails point-in-time, historical non-reuse, benchmark execution,
research-live parity, and current-capital fundability. No threshold in this feature is chosen to
make that family pass.

## Alternatives Rejected

- **Keep v3 unchanged**: controls false positives but has unusably low power and can make the system wait forever.
- **Remove multiplicity controls**: would invite repeated-search false positives.
- **Use all 752 raw rows as independent tests**: ignores their nested family structure and double-counts parameter selection.
- **Make DSR 0.95 the only gate**: remains weak under correlated candidates and does not verify holdout evidence.
- **Lower thresholds until current options passes**: outcome fitting and explicitly prohibited.
