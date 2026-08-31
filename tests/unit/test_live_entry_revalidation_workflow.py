from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LIVE = ROOT / ".github" / "workflows" / "rebalance-live-canary.yml"
LIVENESS = ROOT / ".github" / "workflows" / "pipeline-liveness.yml"


def test_live_order_revalidates_before_signing_or_gateway_call() -> None:
    text = LIVE.read_text(encoding="utf-8")
    revalidate = text.index("Revalidate latest edge before the first strategy fill")
    authorize = text.index("Authorize request — scheduled runs place real orders")
    assert revalidate < authorize
    assert "scripts/live_entry_revalidation_probe.py" in text
    assert "steps.entry_revalidation.outputs.allowed == 'true'" in text
    assert "automation/profit-evidence-engine-last-run" in text
    assert "automation/autonomous-strategy-factory-last-run" in text
    assert "--factory-evidence-json /tmp/capital_entry_evidence.json" in text
    assert "--operational-evidence-json /tmp/operational_canary_evidence.json" in text
    assert "--expected-code-commit \"${GITHUB_SHA}\"" in text
    assert "--sentinel automation/rebalance-live.request" in text
    assert "--live-portfolio deploy/canary-live-portfolio.toml" in text
    assert "--validated-portfolio deploy/global-trend-fixed-portfolio.toml" in text
    assert "observe exploration-canary" in text
    assert "live-canary-profit ${CAP}" in text
    assert "observe live-canary-preview ${CAP}" in text
    assert "--fundability-preview-json /tmp/entry_fundability_preview.json" in text
    assert "observe execution-proxy-parity" in text
    assert "--execution-proxy-parity-json /tmp/entry_execution_proxy_parity.json" in text
    assert '--capital-usd "${CAP}"' in text
    assert "fundability_exit" in text
    assert "proxy_parity_exit" in text


def test_live_order_closes_fill_profit_and_reconciliation_evidence() -> None:
    text = LIVE.read_text(encoding="utf-8")
    assert "live-canary-fills" in text
    assert "Measure live track after real orders" in text
    assert "Reconcile account after the order attempt" in text
    assert '"reconciliation-halt-recovery"' in text
    assert "첫 체결 전 최신 엣지 재검증" in text
    assert "사후 계좌 정합성" in text


def test_liveness_retries_exact_ref_before_missing() -> None:
    text = LIVENESS.read_text(encoding="utf-8")
    assert '"+refs/heads/${branch}:refs/remotes/origin/${branch}"' in text
    assert text.index("git fetch --depth=1 origin") < text.index("사이드카 없음 → MISSING")
