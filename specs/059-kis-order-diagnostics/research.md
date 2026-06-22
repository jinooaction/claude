# Research: KIS Order Diagnostics

## Decision: Keep micro GTAA on the normal-order path only during US regular hours

**Rationale**: KIS publishes separate examples for normal overseas-stock orders, US reservation orders, and US daytime orders. The reservation sample describes the off-hours reservation API and its US reservation window, while the normal order sample uses `/uapi/overseas-stock/v1/trading/order`. The failed run occurred at `2026-06-22 16:04:06 KST`, which was outside the US regular session. The correct immediate fix is to block the normal-order live step outside regular hours, not silently switch to a different endpoint.

**Alternatives considered**:
- Automatically use reservation order outside regular hours: rejected because reservation orders have different endpoint, TR IDs, timing, margin behavior, and failure semantics. This needs its own spec.
- Allow broker rejection to decide: rejected because it recreates the previous evidence loss and may still call a mutating endpoint.

Sources:
- KIS normal order sample: `https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/overseas_stock/order/order.py`
- KIS reservation order sample: `https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/overseas_stock/order_resv/order_resv.py`
- KIS daytime order sample: `https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/overseas_stock/daytime_order/daytime_order.py`

## Decision: Add KIS normal-order fields required by the official sample

**Rationale**: The current normal-order sample validates `ord_svr_dvsn_cd` as required and sends `CTAC_TLNO`, `MGCO_APTM_ODNO`, `SLL_TYPE`, `ORD_SVR_DVSN_CD`, and `ORD_DVSN` in the body. Our current request omitted those optional-looking but officially present fields, including the explicitly required order-server division field. Adding the official defaults removes a confirmed internal mismatch before any retry.

**Alternatives considered**:
- Add only `ORD_SVR_DVSN_CD`: rejected because the official sample's request shape includes the neighboring fields, and matching the sample makes future drift easier to test.
- Leave payload unchanged and rely on KIS accepting missing fields: rejected because the sample currently says the field is required.

## Decision: Store structured diagnostics in the audit payload

**Rationale**: The previous run only preserved `httpx.HTTPStatusError`'s string, losing the response body. A future failure must keep HTTP status, endpoint, KIS response fields, body preview, and sanitized request shape. Keeping this in the existing append-only order rejection payload makes the evidence durable and queryable.

**Alternatives considered**:
- Store diagnostics only in GitHub Actions logs: rejected because logs are not the canonical trading audit surface and may expire.
- Store diagnostics only in `broker_message` as prose: rejected because parsing by the next session would be brittle.

## Decision: Mask before publishing diagnostics

**Rationale**: Diagnostics need request context but must not expose account numbers or credentials. The request body contains `CANO` and `ACNT_PRDT_CD`; headers can contain tokens and app keys. Sanitization must run before data reaches audit payload or sidecar output.

**Alternatives considered**:
- Omit request summary entirely: rejected because request-shape mismatch was one of the confirmed defects.
- Store raw request locally but not in sidecar: rejected because any persistent raw account number would violate secret isolation expectations.

## Decision: Compute micro preflight from preview notional and read-only KIS cash

**Rationale**: The workflow already creates a dry-run preview before live submission. The preflight can sum BUY routed quantity times limit price from that preview and compare it to same-run KIS purchasable cash plus a conservative buffer. This is enough to block obvious insufficient-cash attempts before a mutating order call.

**Alternatives considered**:
- Use the previous day's KIS smoke cash: rejected because cash is drift-prone and already stale in the incident.
- Trust configured `capital_usd`: rejected because configured capital is an intent, not broker-verified buying power.
