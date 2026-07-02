# Data Model: 주문 거부·체결 품질 손익 관측

## ExecutionQualityReport

| Field | Type | Description |
|-------|------|-------------|
| `schema_version` | string | Report schema version, initially `1.0`. |
| `run_id` | string | Workflow or local run id. |
| `commit` | string | Source commit used to run the probe. |
| `timestamp_utc` | string | UTC generation time. |
| `overall_status` | string | `OBSERVE`, `STRATEGY_REVIEW`, `EXECUTION_REVIEW`, or `MISSING_EVIDENCE`. |
| `opportunity_monitor` | object | Monitor verdict, latest signal, cumulative PnL, counts, latest run, next action. |
| `broker_rejections` | object | Parsed rejected-order reason summary from opportunity history. |
| `broker_smoke` | object | Latest KIS smoke state and inferred smoke pass/fail counts. |
| `live_gate` | object | Latest micro GTAA pre-live intent gate if present. |
| `evidence_surfaces` | array | Presence and parse status for consumed sidecars. |
| `safety_invariants` | array | Read-only safety boundary text. |

## OpportunityMonitorSummary

| Field | Type | Description |
|-------|------|-------------|
| `verdict` | string | Existing 064번 monitor verdict. |
| `latest_signal` | string | `INTENT_GAIN`, `INTENT_LOSS`, or `FLAT_OR_UNVALUED`. |
| `cumulative_pnl_usd` | string | Total intended-order mark PnL string from monitor. |
| `valued_records` | integer | Number of valued historical records. |
| `rejected_orders` | integer | Number of rejected orders in monitor counts. |
| `valued_orders` | integer | Number of valued orders in monitor counts. |
| `latest_run_id` | string or null | Latest contributing run id. |
| `next_action_ko` | string | Existing monitor next action text. |

## BrokerRejectionSummary

| Field | Type | Description |
|-------|------|-------------|
| `rejected_orders` | integer | Sum of rejected rows found in opportunity history. |
| `parsed_broker_errors` | integer | Rows where broker reason JSON exposed a broker error code or exception type. |
| `unparsed_reasons` | integer | Rows with reason text that could not be parsed as broker JSON. |
| `broker_error_observation_rate` | string | `parsed_broker_errors / rejected_orders` as a fixed precision decimal when denominator exists. |
| `kis_msg_codes` | object | Count by KIS `msg_cd`. |
| `exception_types` | object | Count by exception type. |
| `http_statuses` | object | Count by HTTP status if present. |

## BrokerSmokeSummary

| Field | Type | Description |
|-------|------|-------------|
| `present` | boolean | Whether latest KIS smoke sidecar was available. |
| `timestamp_utc` | string or null | Smoke sidecar timestamp. |
| `smoke_state` | string | `success`, `failed`, `setup_pending`, or `unknown`. |
| `smoke_exit` | integer or null | Smoke exit code if present. |
| `tests_total` | integer or null | Parsed pytest total count if present. |
| `tests_failed` | integer or null | Parsed failed/error count if present. |
| `smoke_error_rate` | string or null | Failed tests divided by total tests when inferable. |
| `key_valid` | boolean or null | Whether smoke sidecar reported valid SSH/key setup. |

## EvidenceSurface

| Field | Type | Description |
|-------|------|-------------|
| `key` | string | `opportunity-monitor`, `opportunity-history`, `rebalance-micro-gtaa`, or `kis-smoke`. |
| `source_ref` | string | `<branch>:<filename>`. |
| `present` | boolean | Input sidecar exists. |
| `parse_status` | string | `ok`, `present`, `missing`, or `malformed`. |
| `summary_ko` | string | Short Korean summary without secrets. |
