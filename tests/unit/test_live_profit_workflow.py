"""Spec 143 live-profit observation and workflow chain contracts."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"


def _read(name: str) -> str:
    return (WORKFLOWS / name).read_text(encoding="utf-8")


def test_live_profit_workflow_is_fixed_read_only_observation() -> None:
    text = _read("live-profit-evidence.yml")

    assert '"live-canary-fills"' in text
    assert "order_start_date" in text
    assert "order_end_date" in text
    assert 'remote_command="live-canary-fills ${ORDER_START_DATE} ${ORDER_END_DATE}"' in text
    assert '"live-canary-profit ${CAP}"' in text
    assert "Resolve positive measurement capital without changing live authority" in text
    assert '"observe account-nav"' in text
    assert "steps.measurement_capital.outputs.value" in text
    assert "measurement_capital" in text
    assert "Decimal(str(value)):.2f" in text
    assert "live-canary-order" not in text
    assert "--confirm-live" not in text
    assert "rebalance-once" not in text
    assert "automation/live-profit-evidence-last-run" in text
    assert "profit_evidence.json" in text
    assert "continue-on-error: true" in text


def test_live_profit_observation_runs_after_canary_and_on_market_schedules() -> None:
    text = _read("live-profit-evidence.yml")

    assert '"Live canary portfolio rebalance (guarded, real money)"' in text
    assert 'cron: "30 15,17,19 * * 1-5"' in text
    assert "workflow_dispatch:" in text


def test_live_profit_money_and_capital_workflow_chain_is_exact() -> None:
    live_profit = _read("live-profit-evidence.yml")
    money_path = _read("money-path.yml")
    capital = _read("capital-path-readiness.yml")

    assert "name: Live profit evidence (실계좌 체결과 첫 수익 증거)" in live_profit
    assert '"Live profit evidence (실계좌 체결과 첫 수익 증거)"' in money_path
    assert "name: Money-path readiness (첫-자본까지의 길 종합)" in money_path
    assert '"Money-path readiness (첫-자본까지의 길 종합)"' in capital


def test_live_profit_fixed_commands_are_installed_by_ssh_boundary() -> None:
    repair = (ROOT / "deploy" / "repair-ssh-boundary.sh").read_text(encoding="utf-8")
    helper = (ROOT / "deploy" / "live-canary-on-instance.sh").read_text(
        encoding="utf-8"
    )

    assert "live-canary-fills)" in repair
    assert "live-canary-fills\\ *)" in repair
    assert "live-canary-profit\\ *)" in repair
    assert "auto-invest-live-canary fills" in repair
    assert "auto-invest-live-canary profit" in repair
    assert "fills --sync" in helper
    assert "--opening-positions deploy/live-opening-positions.toml" in helper
    assert "performance" in helper
