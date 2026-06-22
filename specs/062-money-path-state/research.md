# Research: Money Path State Guard

## Decision: Extend money-path instead of adding a new status file

**Rationale**: `money_path` already exists to answer "where is real money readiness now?" and is watched by pipeline liveness. The incident happened because the newer micro GTAA live path was not represented at the top of that surface. A separate `MONEY_PATH_STATUS.md` would create another place that can drift.

**Alternatives considered**:
- Static `MONEY_PATH_STATUS.md`: rejected because it becomes stale unless every money-path change updates it.
- Handoff-only update: rejected because handoff has long history and was part of the confusion.
- New independent script: rejected because it duplicates parsing and status logic already present in `money_path_probe.py`.

## Decision: Sentinel is authoritative for arming state

**Rationale**: The current live intent lives in `automation/rebalance-micro-gtaa.request`. Sidecars describe the last execution and may be old or predate #378. The report must classify `armed:true` from the sentinel, then attach last-run evidence as supporting context.

**Alternatives considered**:
- Use only the latest sidecar: rejected because a last `push` run can be preview-only even while the next schedule can submit live orders.
- Use KIS smoke cash as the primary signal: rejected because it is a preflight input, not arming intent.

## Decision: Next scheduled live attempt is computed from the workflow schedule

**Rationale**: The micro GTAA workflow schedule is fixed at weekdays 15:00 UTC. Reporting the next possible automatic live attempt makes "tonight" concrete without dispatching anything.

**Alternatives considered**:
- Ask GitHub Actions for the next run: rejected because the report must work offline from repository and sidecar evidence.
- Leave next run as prose: rejected because relative dates caused confusion.

## Decision: Last live outcome must separate route entry from fill

**Rationale**: The last manual run entered the live order path but KIS rejected both orders. The report must say both facts together so "actual money path ran" is not mistaken for "orders filled".

**Alternatives considered**:
- Collapse to success/failure: rejected because GitHub job success can contain broker rejections.
