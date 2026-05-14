# Contract — Property-Fuzz Protocol

**Author**: spec 007 (this PR)
**Producer**: `auto_invest.canary.fuzz`
**Consumers**: `auto_invest.canary.run.run_canary`; `tests/unit/test_canary_fuzz.py` (the meta-test that asserts the protocol works).

## Target

The fuzz target is **`auto_invest.risk.gates`** (the K1 module). Four functions are exercised:

- `per_trade_cap_gate(request, caps, quote_price) -> GateDecision`
- `per_symbol_cap_gate(request, caps, quote_price, current_symbol_exposure_usd) -> GateDecision`
- `global_exposure_gate(request, caps, quote_price, current_global_exposure_usd) -> GateDecision`
- `whitelist_gate(request, whitelist) -> GateDecision` — included for completeness; tests that an allow decision implies the symbol IS on the whitelist.

The functions are imported from `auto_invest.risk.gates` UNCHANGED. The fuzz harness does not patch or wrap them.

## Hypothesis strategies (in `auto_invest.canary.fuzz`)

```python
qty_strategy = st.integers(min_value=1, max_value=10_000)

price_strategy = st.decimals(
    min_value=Decimal("0.01"),
    max_value=Decimal("10000.00"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)

exposure_pct_strategy = st.decimals(
    min_value=Decimal("0.0"),
    max_value=Decimal("1.0"),
    places=4,
    allow_nan=False,
    allow_infinity=False,
)

sizing_caps_strategy = st.builds(
    SizingCaps,
    per_trade_cap_pct=st.decimals(min_value=Decimal("0.001"), max_value=Decimal("0.5"), places=4),
    per_symbol_cap_pct=st.decimals(min_value=Decimal("0.005"), max_value=Decimal("0.8"), places=4),
    global_cap_pct=st.decimals(min_value=Decimal("0.01"), max_value=Decimal("1.0"), places=4),
    total_capital_usd=st.decimals(min_value=Decimal("1000"), max_value=Decimal("10_000_000"), places=2),
).filter(lambda c: c.per_trade_cap_pct <= c.per_symbol_cap_pct <= c.global_cap_pct)

order_request_strategy = st.builds(
    OrderRequest,
    qty=qty_strategy,
    side=st.sampled_from([Side.BUY, Side.SELL]),
    limit_price_usd=price_strategy,
    # ... other OrderRequest fields with stable defaults
)
```

## Property (post-condition)

```python
@given(
    request=order_request_strategy,
    caps=sizing_caps_strategy,
    quote=price_strategy,
    current_symbol_exposure=exposure_pct_strategy,
    current_global_exposure=exposure_pct_strategy,
)
@settings(max_examples=10_000, deadline=None, suppress_health_check=[HealthCheck.too_slow])
def cap_chain_monotonicity(request, caps, quote, current_symbol_exposure, current_global_exposure):
    # The order value implied by this request:
    order_value_usd = quote * Decimal(request.qty)

    per_trade  = per_trade_cap_gate(request, caps, quote)
    per_symbol = per_symbol_cap_gate(
        request, caps, quote,
        current_symbol_exposure_usd=current_symbol_exposure * caps.total_capital_usd,
    )
    glob = global_exposure_gate(
        request, caps, quote,
        current_global_exposure_usd=current_global_exposure * caps.total_capital_usd,
    )

    # The mathematical post-condition under test:
    if per_trade.allow:
        # An allowed per_trade decision implies the order value fits the per-trade cap.
        assert order_value_usd <= caps.per_trade_cap_pct * caps.total_capital_usd, \
            "K1 violation: per_trade gate allowed an over-cap order"

    if per_symbol.allow:
        assert (current_symbol_exposure * caps.total_capital_usd + order_value_usd) <= \
            (caps.per_symbol_cap_pct * caps.total_capital_usd), \
            "K1 violation: per_symbol gate allowed exceeding the per-symbol cap"

    if glob.allow:
        assert (current_global_exposure * caps.total_capital_usd + order_value_usd) <= \
            (caps.global_cap_pct * caps.total_capital_usd), \
            "K1 violation: global gate allowed exceeding the global cap"

    # Chain monotonicity: per_trade.allow ⇒ order_value ≤ per_trade_cap ≤ per_symbol_cap ≤ global_cap.
    # This is true by construction of sizing_caps_strategy's filter; this assertion makes the strategy itself a property-checked invariant.
    assert caps.per_trade_cap_pct <= caps.per_symbol_cap_pct <= caps.global_cap_pct
```

## Collection contract

Hypothesis is invoked NOT via pytest but programmatically via `hypothesis.core.execute_explicit_examples`-style adapter so the canary fuzz pass:

1. Runs ALL `--iterations` examples (does not stop on first failure).
2. Captures every failing example as a `FuzzCounterexample` (per data-model.md).
3. Writes the captured set to `data/canary/<run_id>/property-fuzz/counterexamples.json`.
4. Returns `0` iff `len(counterexamples) == 0`, else `1`.

The Hypothesis database is held in-memory only (`InMemoryExampleDatabase`); we DO NOT persist shrunk examples between runs because reproducibility (SC-C04) demands seed-only state, not example database.

## Seed contract

`seed_bundle.hypothesis_database_seed` is passed to `hypothesis.given(...)` via Hypothesis's `derandomize=False, seed=<seed>` mechanism. Two runs with the same seed produce the same `(generated, shrunk)` example sequence. If the operator hits a reproducibility bug, the seed in `seeds.txt` is the recovery key.

## Future extension (out of scope for v1)

A future spec may add stateful fuzz (Hypothesis `RuleBasedStateMachine`) that exercises the full order pipeline (multiple symbols, intermixed buy/sell, halt transitions). That would target the integrated behaviour rather than the K1 math. v1 spec 007 keeps pure-math fuzz only because:

- Integrated fuzz is largely redundant with synthetic-shock replay (which is integrated, deterministic, and human-readable).
- Pure-math fuzz at the K1 boundary is the highest-leverage signal for off-by-one bugs (SC-C02).
- Pure-math shrinking produces minimal counterexamples; integrated shrinking is famously hard.
