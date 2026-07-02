# Data Model: 공개 데이터 교차 검증 확장

## PublicDataSource

- `kind`: provider name such as `fred`, `treasury`, `dbnomics`
- `id`: provider-specific series identifier
- `request_mode`: source-specific request behaviour, including user-agent mode where needed
- `validation`: row count, freshness, parse, and missing-value checks
- Relationships: produces one `PublishedSeries` when validation passes

## PublishedSeries

- `registry_key`: `provider:id`, for example `fred:DGS10`
- `published_path`: CSV path under the research-only output directory
- `first_date`
- `last_date`
- `rows`
- `missing`
- Relationships: can be referenced by zero or more `CrossCheckPair`

## CrossCheckPair

- `kind`: `levels` for this feature
- `a`: first registry key
- `b`: second registry key
- `tolerance`
- `min_overlap`
- `min_agree_pct`
- `status`: PASS, FAIL, SKIPPED, or INSUFFICIENT_OVERLAP
- Relationships: reads two `PublishedSeries` registry entries

## CollectionSummary

- `overall_ok`
- `published`
- `total_items`
- `items`
- `cross_checks`
- `probes`
- `isolation_note`
- Relationships: consumed by automation sidecars, candidate factory, and operator handoff

## State Transitions

- Source configured -> request attempted -> parse succeeds -> validation passes -> published -> registry key available
- Source configured -> request/parse/validation fails -> item failed -> no registry key -> dependent cross-check SKIPPED
- Both registry keys available -> cross-check PASS or FAIL -> `overall_ok` reflects failure state
