from __future__ import annotations

from auto_invest.analytics.research_family_audit import (
    annotate_research_families,
    build_research_family_audit,
    classify_research_family,
)


def _row(candidate_id: str, index: int, **extra: str) -> dict[str, str]:
    return {
        "candidate_id": f"{candidate_id}-{index:03d}",
        "strategy_fingerprint": f"sha256:{candidate_id}-{index:03d}",
        "status": "complete",
        **extra,
    }


def _production_shape() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for batch in ("a", "b", "c", "d"):
        rows.extend(
            _row("factory-trend", index, batch_id=f"strategy-factory-{batch}")
            for index in range(64)
        )
    for batch in ("mild-tilt", "price-overlay", "strong-rotation"):
        rows.extend(
            _row("exploratory-candidate", index, exploration_batch_id=batch)
            for index in range(64)
        )
    rows.extend(_row("macro-cycle", index) for index in range(64))
    rows.extend(_row("treasury-carry", index) for index in range(64))
    rows.extend(_row("credit-spread", index) for index in range(64))
    for prefix in (
        "fx-carry",
        "commodity-carry",
        "commodity-positioning-signal",
        "commodity-supply-demand-signal",
        "usda-crop-signal",
        "energy-cross-signal",
        "options-vrp-signal",
    ):
        rows.extend(_row(prefix, index) for index in range(16))
    return rows


def test_production_shape_reconstructs_752_rows_as_17_families() -> None:
    rows = annotate_research_families(_production_shape())
    audit = build_research_family_audit(rows)

    assert len(rows) == 752
    assert len(audit) == 17
    assert sum(row["candidate_count"] for row in audit) == 752
    assert all(row["candidate_identity_digest"].startswith("sha256:") for row in audit)


def test_classifier_uses_batch_identity_before_candidate_prefix() -> None:
    assert (
        classify_research_family(
            _row("factory-trend", 1, batch_id="strategy-factory-frozen")
        )
        == "legacy-factory:strategy-factory-frozen"
    )
    assert (
        classify_research_family(
            _row("exploratory-candidate", 1, exploration_batch_id="mild-tilt")
        )
        == "legacy-exploration:mild-tilt"
    )


def test_unknown_candidate_fails_closed() -> None:
    try:
        annotate_research_families([_row("unknown-family", 1)])
    except ValueError as exc:
        assert "unclassified research candidate" in str(exc)
    else:
        raise AssertionError("unknown research family was accepted")


def test_audit_digest_is_order_independent_but_identity_sensitive() -> None:
    rows = annotate_research_families([_row("fx-carry", 1), _row("fx-carry", 2)])
    original = build_research_family_audit(rows)
    reordered = build_research_family_audit(list(reversed(rows)))
    mutated = [dict(row) for row in rows]
    mutated[0]["strategy_fingerprint"] = "sha256:changed"

    assert original == reordered
    assert original != build_research_family_audit(mutated)
