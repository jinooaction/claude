"""Deterministic research-family reconstruction for the cumulative audit ledger."""

from __future__ import annotations

import hashlib
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from typing import Any

_PREFIX_FAMILIES = (
    ("accounting-factor-", "equity-accounting-cross-sectional-factors"),
    ("calendar-turn-", "equity-calendar-turn-of-month"),
    ("regime-", "regime-adaptive-stock-bond-joint-weakness"),
    ("commodity-positioning-", "commodity-positioning"),
    ("commodity-supply-demand-", "commodity-supply-demand"),
    ("commodity-", "commodity-term-structure"),
    ("energy-cross-", "energy-cross-market"),
    ("options-vrp-", "options-variance-risk-premium"),
    ("usda-crop-", "usda-crop-supply-demand"),
    ("treasury-", "treasury-carry"),
    ("credit-", "credit-spread"),
    ("macro-", "macro-regime"),
    ("fx-", "fx-carry"),
)


def _nonempty(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def classify_research_family(row: Mapping[str, object]) -> str:
    """Derive family identity from immutable batch or candidate identity fields."""

    batch_id = _nonempty(row.get("batch_id"))
    if batch_id is not None:
        return f"legacy-factory:{batch_id}"
    exploration_batch_id = _nonempty(row.get("exploration_batch_id"))
    if exploration_batch_id is not None:
        return f"legacy-exploration:{exploration_batch_id}"
    candidate_id = _nonempty(row.get("candidate_id"))
    if candidate_id is not None:
        for prefix, family_id in _PREFIX_FAMILIES:
            if candidate_id.startswith(prefix):
                return family_id
    raise ValueError(f"unclassified research candidate: {candidate_id or '<missing>'}")


def annotate_research_families(
    rows: Sequence[Mapping[str, object]],
) -> list[dict[str, Any]]:
    """Copy rows and attach the independently derived family identifier."""

    return [
        {**dict(row), "research_family_id": classify_research_family(row)} for row in rows
    ]


def build_research_family_audit(
    rows: Sequence[Mapping[str, object]],
) -> list[dict[str, Any]]:
    """Build an order-independent family summary from raw audit identities."""

    grouped: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[classify_research_family(row)].append(row)

    output: list[dict[str, Any]] = []
    for family_id, family_rows in sorted(grouped.items()):
        identities: list[str] = []
        statuses: Counter[str] = Counter()
        for row in family_rows:
            candidate_id = _nonempty(row.get("candidate_id"))
            fingerprint = _nonempty(row.get("strategy_fingerprint"))
            status = _nonempty(row.get("status"))
            if candidate_id is None or fingerprint is None or status is None:
                raise ValueError(f"incomplete research audit identity in {family_id}")
            identities.append(f"{candidate_id}|{fingerprint}")
            statuses[status] += 1
        digest = hashlib.sha256("\n".join(sorted(identities)).encode()).hexdigest()
        output.append(
            {
                "research_family_id": family_id,
                "candidate_count": len(family_rows),
                "candidate_identity_digest": f"sha256:{digest}",
                "status_counts": dict(sorted(statuses.items())),
            }
        )
    return output


__all__ = [
    "annotate_research_families",
    "build_research_family_audit",
    "classify_research_family",
]
