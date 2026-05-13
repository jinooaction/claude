"""KPI aggregation over `token_usage` (FR-T05, FR-T07, FR-T09).

Returns an `EfficiencySnapshot` covering a configurable window. The
output is byte-stable for the same input rows (SC-T04) so 005's
autonomous tuner can diff snapshots reproducibly.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Literal

from auto_invest.telemetry.thresholds import KPI_DIRECTIONS, TierTable

Direction = Literal["higher_is_better", "lower_is_better"]


@dataclass(frozen=True)
class KPI:
    name: str
    value: Decimal
    tier: str  # "A" | "B" | "C" | "N/A"
    direction: Direction
    threshold_used: dict[str, str]


@dataclass(frozen=True)
class EfficiencySnapshot:
    window_start_utc: str
    window_end_utc: str
    call_count: int
    kpis: list[KPI]
    per_decision_class: dict[str, dict[str, Any]] = field(default_factory=dict)
    top_n_calls: list[dict[str, Any]] = field(default_factory=list)


def _percentile(values: list[int], pct: float) -> Decimal:
    """Nearest-rank percentile. Returns 0 on empty input."""
    if not values:
        return Decimal(0)
    ordered = sorted(values)
    # nearest-rank: ceil(pct/100 * N) - 1 (zero-indexed)
    rank = max(1, int(-(-pct * len(ordered) // 100))) - 1
    return Decimal(ordered[min(rank, len(ordered) - 1)])


def _decimal_or_zero(text: str | None) -> Decimal:
    if text is None or text == "":
        return Decimal(0)
    try:
        return Decimal(text)
    except Exception:
        return Decimal(0)


def compute_snapshot(
    conn: sqlite3.Connection,
    *,
    window_start_utc: str,
    window_end_utc: str,
    tiers: TierTable,
    top_n: int = 5,
) -> EfficiencySnapshot:
    """Aggregate token_usage rows whose ts_utc is in [start, end)."""
    rows = conn.execute(
        """
        SELECT seq, ts_utc, model, decision_class,
               input_tokens, output_tokens,
               cache_read_tokens, cache_write_tokens,
               cost_usd, latency_ms
        FROM token_usage
        WHERE ts_utc >= ? AND ts_utc < ?
        ORDER BY seq
        """,
        (window_start_utc, window_end_utc),
    ).fetchall()

    call_count = len(rows)

    if call_count == 0:
        kpis = [
            KPI(
                name=name,
                value=Decimal(0),
                tier="N/A",
                direction=KPI_DIRECTIONS[name],
                threshold_used=tiers.thresholds_for(name),
            )
            for name in KPI_DIRECTIONS
        ]
        return EfficiencySnapshot(
            window_start_utc=window_start_utc,
            window_end_utc=window_end_utc,
            call_count=0,
            kpis=kpis,
            per_decision_class={},
            top_n_calls=[],
        )

    sum_input = sum(r["input_tokens"] for r in rows)
    sum_cache_read = sum(r["cache_read_tokens"] for r in rows)
    sum_cost = sum((_decimal_or_zero(r["cost_usd"]) for r in rows), Decimal(0))
    tokens_per_call = [
        r["input_tokens"] + r["output_tokens"] + r["cache_read_tokens"] + r["cache_write_tokens"]
        for r in rows
    ]
    latencies = [int(r["latency_ms"]) for r in rows]

    cache_denom = sum_input + sum_cache_read
    cache_hit_rate = (
        (Decimal(sum_cache_read) / Decimal(cache_denom)).quantize(Decimal("0.0001"))
        if cache_denom > 0
        else Decimal(0)
    )
    tokens_p95 = _percentile(tokens_per_call, 95.0)
    usd_per_decision_mean = (sum_cost / Decimal(call_count)).quantize(Decimal("0.000001"))
    latency_p95 = _percentile(latencies, 95.0)

    kpi_values: dict[str, Decimal] = {
        "cache_hit_rate": cache_hit_rate,
        "tokens_per_decision_p95": tokens_p95,
        "usd_per_decision_mean": usd_per_decision_mean,
        "latency_p95_ms": latency_p95,
    }
    kpis = [
        KPI(
            name=name,
            value=value,
            tier=tiers.classify(name, value),
            direction=KPI_DIRECTIONS[name],
            threshold_used=tiers.thresholds_for(name),
        )
        for name, value in kpi_values.items()
    ]

    # per_decision_class aggregate (sorted alphabetically for stability).
    classes: dict[str, list[sqlite3.Row]] = {}
    for r in rows:
        key = r["decision_class"] or "(unclassified)"
        classes.setdefault(key, []).append(r)
    per_decision_class: dict[str, dict[str, Any]] = {}
    for key in sorted(classes):
        bucket = classes[key]
        bucket_tokens = [
            r["input_tokens"]
            + r["output_tokens"]
            + r["cache_read_tokens"]
            + r["cache_write_tokens"]
            for r in bucket
        ]
        bucket_cost = sum((_decimal_or_zero(r["cost_usd"]) for r in bucket), Decimal(0))
        per_decision_class[key] = {
            "count": len(bucket),
            "tokens_total": sum(bucket_tokens),
            "cost_usd": str(bucket_cost.quantize(Decimal("0.000001"))),
            "p95_tokens": int(_percentile(bucket_tokens, 95.0)),
        }

    # top_n_calls by cost descending; ties broken by seq descending for stability.
    sorted_rows = sorted(
        rows,
        key=lambda r: (_decimal_or_zero(r["cost_usd"]), int(r["seq"])),
        reverse=True,
    )
    top_n_calls = [
        {
            "seq": int(r["seq"]),
            "ts_utc": r["ts_utc"],
            "model": r["model"],
            "decision_class": r["decision_class"],
            "tokens_total": int(
                r["input_tokens"]
                + r["output_tokens"]
                + r["cache_read_tokens"]
                + r["cache_write_tokens"]
            ),
            "cost_usd": r["cost_usd"],
        }
        for r in sorted_rows[:top_n]
    ]
    return EfficiencySnapshot(
        window_start_utc=window_start_utc,
        window_end_utc=window_end_utc,
        call_count=call_count,
        kpis=kpis,
        per_decision_class=per_decision_class,
        top_n_calls=top_n_calls,
    )


__all__ = ["EfficiencySnapshot", "KPI", "compute_snapshot"]
