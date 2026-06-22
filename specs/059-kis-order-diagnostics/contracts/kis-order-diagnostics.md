# Contract: KIS Order Diagnostics

## KIS Normal Order Body

Endpoint:

```text
POST /uapi/overseas-stock/v1/trading/order
```

Required body keys for US normal limit orders:

```json
{
  "CANO": "********",
  "ACNT_PRDT_CD": "**",
  "OVRS_EXCG_CD": "NASD",
  "PDNO": "IEF",
  "ORD_QTY": "1",
  "OVRS_ORD_UNPR": "94.55",
  "CTAC_TLNO": "",
  "MGCO_APTM_ODNO": "",
  "SLL_TYPE": "",
  "ORD_SVR_DVSN_CD": "0",
  "ORD_DVSN": "00"
}
```

Rules:
- Buy orders set `SLL_TYPE` to an empty string.
- Sell orders set `SLL_TYPE` to `00`.
- Micro GTAA uses normal limit orders only, so `ORD_DVSN` is `00`.
- Reservation and daytime endpoints are not used by this feature.

## Broker Diagnostics Shape

`ORDER_REJECTED_BY_BROKER` payload includes:

```json
{
  "event_type": "ORDER_REJECTED_BY_BROKER",
  "broker_code": "KisOrderError",
  "broker_message": "KIS order request failed",
  "diagnostics": {
    "exception_type": "HTTPStatusError",
    "http_status": 500,
    "method": "POST",
    "endpoint": "/uapi/overseas-stock/v1/trading/order",
    "kis_rt_cd": "1",
    "kis_msg_cd": "APBK0000",
    "kis_msg1": "broker message",
    "request_summary": {
      "tr_id": "TTTT1002U",
      "body": {
        "CANO": "******78",
        "ACNT_PRDT_CD": "**",
        "PDNO": "IEF",
        "ORD_QTY": "1"
      }
    }
  }
}
```

Rules:
- Account and credential values must be masked.
- `response_body_preview` is length-limited.
- Missing or non-JSON response bodies still produce diagnostics.

## Micro GTAA Workflow Preflight

Path: `.github/workflows/rebalance-micro-gtaa-canary.yml`

Required behavior:
- A preflight step runs after dry-run preview and before the circuit breaker/live steps.
- It writes `/tmp/micro_preflight.json`.
- It sets output `ok=true` only when:
  - event is not `push`,
  - XNYS regular session is open,
  - planned buy notional is known,
  - read-only KIS purchasable cash is known,
  - purchasable cash is at least planned notional plus fee buffer.
- The circuit breaker step and live step require `steps.preflight.outputs.ok == 'true'`.
- The sidecar includes the preflight JSON section.

## Test Contract

Required automated checks:
- Broker payload tests cover buy and sell normal orders.
- Broker diagnostics tests cover JSON and non-JSON HTTP errors.
- Secret masking tests cover account body fields and credential-like keys.
- Workflow tests prove the preflight step exists before the live step, the live condition requires preflight success, and sidecar publishes preflight JSON.
