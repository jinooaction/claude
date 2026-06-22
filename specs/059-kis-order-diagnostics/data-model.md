# Data Model: KIS Order Diagnostics

## OrderPreconditions

Represents the live attempt checks before any micro GTAA broker mutation.

Fields:
- `timestamp_utc`: evaluation time.
- `event`: GitHub event name.
- `session_open`: whether XNYS regular trading session is open.
- `session_reason`: human-readable reason when blocked.
- `planned_buy_notional_usd`: sum of preview BUY routed quantity times limit price.
- `fee_buffer_pct`: conservative buffer applied to planned notional.
- `required_cash_usd`: planned notional plus buffer.
- `purchasable_cash_usd`: read-only KIS purchasable USD cash, if available.
- `ok`: true only when the event, session, and cash checks all pass.

Validation:
- `ok` is false when `event == push`.
- `ok` is false when `session_open` is false.
- `ok` is false when `purchasable_cash_usd` is missing or below `required_cash_usd`.

## KisNormalOrderRequest

Represents the normal overseas-stock order payload sent to KIS.

Fields:
- `CANO`, `ACNT_PRDT_CD`: account parts, masked in diagnostics.
- `OVRS_EXCG_CD`: order exchange code.
- `PDNO`: symbol.
- `ORD_QTY`: integer quantity string.
- `OVRS_ORD_UNPR`: order price string.
- `CTAC_TLNO`: contact phone field; default empty string.
- `MGCO_APTM_ODNO`: manager-appointed order id field; default empty string.
- `SLL_TYPE`: empty for buy, `00` for sell.
- `ORD_SVR_DVSN_CD`: order server division code; default `0`.
- `ORD_DVSN`: order division; `00` for regular limit orders.

Validation:
- Quantity must be positive.
- Limit order must carry a non-empty price.
- Diagnostics must never expose raw `CANO` or credentials.

## BrokerRejectionDiagnostics

Represents durable evidence for a failed broker request.

Fields:
- `exception_type`: Python exception class name.
- `message`: original exception string, length-limited.
- `http_status`: HTTP status code, if present.
- `method`: request method, if present.
- `endpoint`: URL path, without host query secrets.
- `kis_rt_cd`, `kis_msg_cd`, `kis_msg1`: KIS response fields, if present.
- `response_body_preview`: masked, length-limited body preview.
- `response_json`: masked JSON body when parseable and small enough.
- `request_summary`: masked method, endpoint, TR ID, and body field summary.

Validation:
- Masking happens before persistence.
- Body preview has a bounded length.
- Non-JSON bodies still preserve HTTP status and a masked preview.

## MicroRunEvidence

Represents the sidecar-visible run report.

Fields:
- Existing preview, breaker, live result, and measurement sections.
- New `preflight_json` section.
- Broker rejection diagnostics included in live result rows through `reason` or explicit diagnostic fields.

Validation:
- Preflight section is present even when live step is skipped.
- Push-triggered runs show preview-only status.
