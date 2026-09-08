from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from auto_invest.analytics.mobile_operator_snapshot import build_mobile_operator_summaries

NOW = datetime(2026, 9, 8, 0, 0, tzinfo=UTC)


def _write_inputs(root: Path) -> tuple[Path, Path, Path]:
    sidecars = root / "sidecars"
    sidecars.mkdir()
    money = {
        "schema_version": "1.8",
        "as_of_utc": "2026-09-07T23:31:02Z",
        "stage": "DEPLOYED",
        "blocking_gate": "20% 승격은 별도 깨끗한 전진 증거 필요.",
        "current_rung": 1,
        "entry_route": "operational_canary",
        "capital_pct": "10",
        "account_nav_usd": "1434.91",
        "deployed_capital_usd": 143,
        "live_money_state": {
            "status": "REAL_ORDER_PATH_ARMED",
            "can_submit_real_orders": True,
            "capital_usd": 143,
            "next_scheduled_live_utc": "2026-09-08T14:17:00Z",
            "last_run": {
                "timestamp_utc": "2026-09-07T19:09:50Z",
                "event": "schedule",
                "live_step": "failure",
                "preflight_ok": True,
                "preflight_reason": "ENTRY_READY",
                "accepted_or_filled_count": 0,
                "broker_rejected_count": 0,
            },
        },
        "live_profit_evidence": {
            "status": "NO_FILLS_YET",
            "fills_count": 0,
            "gross_invested_usd": "0",
            "realized_pnl_usd": "0",
            "unrealized_pnl_usd": "0",
            "total_pnl_usd": "0",
            "return_pct": None,
            "measurement_scope": "strategy",
            "observed_at_utc": "2026-09-07T22:13:49Z",
        },
        "safety_budget": {
            "reference_rung": 1,
            "current_dd_pct": "0",
            "demote_dd_pct": "10",
            "halt_dd_pct": "20",
            "loss_at_demote_usd": 15,
            "loss_at_halt_usd": 29,
        },
    }
    (sidecars / "money-path.md").write_text(
        "## 결정 JSON\n\n```json\n" + json.dumps(money) + "\n```\n",
        encoding="utf-8",
    )
    revalidation = {
        "allowed": True,
        "evidence": {
            "forward_n_obs": 9,
            "forward_psr": None,
            "min_forward_obs": 40,
            "min_forward_psr": 0.8,
            "operational_assessment": {
                "candidate_id": "globalfixed-ensemble-3-6-9-12",
                "alpha_confirmed": False,
            },
            "fundability": {"target_weights": {"IAUM": "0.16", "SCHX": "0.33"}},
        },
    }
    (sidecars / "rebalance-live-canary.md").write_text(
        "| timestamp_utc | 2026-09-07T19:09:50Z |\n```json\n"
        + json.dumps(revalidation)
        + "\n```\n",
        encoding="utf-8",
    )
    (sidecars / "autonomous-strategy-factory.md").write_text(
        "# 자동 전략 공장\n\n"
        "- 역사 판정: `PUBLISHED_EDGE`\n"
        "- 개발 선택 후보: `pead-candidate`\n\n"
        "| timestamp_utc | 2026-09-07T20:00:00Z |\n",
        encoding="utf-8",
    )
    budget_path = root / "budget.json"
    budget_path.write_text(
        json.dumps(
            {
                "currency": "USD",
                "capital_limit_usd": "600.00",
                "order_limit_usd": "120.00",
                "symbol_limit_usd": "120.00",
                "total_exposure_limit_usd": "480.00",
                "daily_stop_trigger_usd": "12.00",
                "orders_enabled": False,
                "confirmed_on": "2026-09-07",
            }
        ),
        encoding="utf-8",
    )
    preflight_path = root / "preflight.json"
    preflight_path.write_text(
        json.dumps(
            {
                "status": "PREPARATION_CHECKED",
                "live_eligible": False,
                "orders_submitted": 0,
                "blockers": ["VERIFIED_ACCOUNT_NAV_REQUIRED"],
            }
        ),
        encoding="utf-8",
    )
    return sidecars, budget_path, preflight_path


def test_summaries_keep_money_concepts_separate_and_account_unverified(tmp_path: Path) -> None:
    sidecars, budget, preflight = _write_inputs(tmp_path)

    capital, strategy = build_mobile_operator_summaries(
        sidecar_dir=sidecars,
        budget_path=budget,
        preflight_path=preflight,
        now=NOW,
    )

    assert capital["account"]["status"] == "UNVERIFIED"
    assert capital["account"]["total_assets_usd"] is None
    assert capital["account"]["purchasable_cash_usd"] is None
    assert capital["live_allocation"]["allocated_capital_usd"] == "143"
    assert capital["intraday_budget"]["capital_limit_usd"] == "600.00"
    assert capital["intraday_budget"]["daily_stop_trigger_usd"] == "12.00"
    assert capital["intraday_budget"]["orders_enabled"] is False
    assert capital["performance"]["fills_count"] == 0
    assert capital["performance"]["gross_invested_usd"] == "0"
    assert capital["performance"]["measurement_scope"] == "strategy"
    assert capital["performance"]["observed_at_utc"] == "2026-09-07T22:13:49Z"
    assert "1434.91" not in json.dumps(capital)

    assert strategy["active"]["strategy_id"] == "globalfixed-ensemble-3-6-9-12"
    assert strategy["active"]["role"] == "OPERATIONAL_CANARY"
    assert strategy["active"]["alpha_confirmed"] is False
    assert strategy["active"]["target_symbols"] == ["IAUM", "SCHX"]
    assert strategy["active"]["forward_observations"] == {"current": 9, "required": 40}
    assert strategy["intraday"]["role"] == "PREPARATION_ONLY"
    assert strategy["intraday"]["live_eligible"] is False
    assert strategy["intraday"]["orders_submitted"] == 0
    assert strategy["intraday"]["confirmed_on"] == "2026-09-07"
    assert strategy["research"]["candidate_id"] == "pead-candidate"
    assert strategy["research"]["promotion_eligible"] is False


def test_direct_profit_sidecar_wins_and_is_strictly_allowlisted(tmp_path: Path) -> None:
    sidecars, budget, preflight = _write_inputs(tmp_path)
    (sidecars / "live-profit-evidence.md").write_text(
        json.dumps(
            {
                "status": "FILLED_NOT_PROFITABLE",
                "measurement_scope": "strategy",
                "observed_at_utc": "2026-09-07T23:59:00Z",
                "fills_count": 2,
                "gross_invested_usd": "178.32",
                "realized_pnl_usd": "-0.10",
                "unrealized_pnl_usd": "0",
                "total_pnl_usd": "-0.10",
                "return_pct": "-0.056",
                "account_number": "must-not-leak",
            }
        ),
        encoding="utf-8",
    )

    capital, _ = build_mobile_operator_summaries(
        sidecar_dir=sidecars,
        budget_path=budget,
        preflight_path=preflight,
        now=NOW,
    )

    assert capital["performance"]["fills_count"] == 2
    assert capital["performance"]["gross_invested_usd"] == "178.32"
    assert capital["performance"]["observed_at_utc"] == "2026-09-07T23:59:00Z"
    assert "must-not-leak" not in json.dumps(capital)


def test_present_but_broken_direct_profit_sidecar_does_not_hide_behind_old_data(
    tmp_path: Path,
) -> None:
    sidecars, budget, preflight = _write_inputs(tmp_path)
    (sidecars / "live-profit-evidence.md").write_text("{bad", encoding="utf-8")

    capital, _ = build_mobile_operator_summaries(
        sidecar_dir=sidecars,
        budget_path=budget,
        preflight_path=preflight,
        now=NOW,
    )

    assert capital["performance"] is None


def test_missing_or_malformed_inputs_fail_closed_without_guessing(tmp_path: Path) -> None:
    sidecars = tmp_path / "sidecars"
    sidecars.mkdir()
    (sidecars / "money-path.md").write_text("## 결정 JSON\n```json\n{bad\n```", encoding="utf-8")
    bad_budget = tmp_path / "budget.json"
    bad_budget.write_text('{"currency":"KRW","capital_limit_usd":"600"}', encoding="utf-8")

    capital, strategy = build_mobile_operator_summaries(
        sidecar_dir=sidecars,
        budget_path=bad_budget,
        preflight_path=None,
        now=NOW,
    )

    assert capital["as_of_utc"] is None
    assert capital["account"]["status"] == "UNVERIFIED"
    assert capital["live_allocation"] is None
    assert capital["intraday_budget"] is None
    assert capital["performance"] is None
    assert capital["risk"] is None
    assert strategy["active"] is None
    assert strategy["intraday"] is None
    assert strategy["research"]["status"] == "MISSING"
    assert strategy["last_execution"] is None


def test_public_summary_contains_no_raw_secrets_or_account_identifiers(tmp_path: Path) -> None:
    sidecars, budget, preflight = _write_inputs(tmp_path)
    (sidecars / "money-path.md").write_text(
        (sidecars / "money-path.md").read_text(encoding="utf-8")
        + '\n{"kis_app_key":"secret","account_number":"123-45","ssh_key":"private"}\n',
        encoding="utf-8",
    )

    summaries = build_mobile_operator_summaries(
        sidecar_dir=sidecars,
        budget_path=budget,
        preflight_path=preflight,
        now=NOW,
    )
    serialized = json.dumps(summaries, ensure_ascii=False).lower()

    for forbidden in (
        "kis_app_key",
        "kis_app_secret",
        "account_number",
        "access_token",
        "ssh_key",
        "123-45",
    ):
        assert forbidden not in serialized


def test_future_source_timestamp_is_preserved_for_app_to_mark_unknown(tmp_path: Path) -> None:
    sidecars, budget, preflight = _write_inputs(tmp_path)
    raw = (sidecars / "money-path.md").read_text(encoding="utf-8")
    raw = raw.replace("2026-09-07T23:31:02Z", "2026-09-09T23:31:02Z")
    (sidecars / "money-path.md").write_text(raw, encoding="utf-8")

    capital, _ = build_mobile_operator_summaries(
        sidecar_dir=sidecars,
        budget_path=budget,
        preflight_path=preflight,
        now=NOW,
    )

    assert capital["as_of_utc"] == "2026-09-09T23:31:02Z"
    assert capital["max_age_minutes"] == 1800
