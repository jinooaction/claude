"""스펙 074 — 후보 가격 이력 지원 manifest 테스트."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from auto_invest.analytics.candidate_history_support import (
    CANDIDATE_RESULT_HISTORY_ROOT,
    candidate_history_datasets,
    history_dataset_for_portfolio,
    manifest_document,
    require_history_root_for_portfolio,
)

ROOT = Path(__file__).resolve().parents[2]
_PROBE_PATH = ROOT / "scripts" / "candidate_history_support_probe.py"

_spec = importlib.util.spec_from_file_location("candidate_history_support_probe", _PROBE_PATH)
assert _spec and _spec.loader
_probe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_probe)
probe_main = _probe.main


def test_candidate_history_manifest_is_deterministic() -> None:
    rows = candidate_history_datasets()
    assert [row.key for row in rows] == [
        "micro-gtaa",
        "global-trend-fixed",
        "global-trend-wide",
        "multi-asset-trend",
    ]
    assert [row.portfolio_path for row in rows] == [
        "deploy/micro-gtaa-live-portfolio.toml",
        "deploy/global-trend-fixed-portfolio.toml",
        "deploy/global-trend-wide-portfolio.toml",
        "deploy/multi-asset-trend-portfolio.toml",
    ]
    assert [row.db_path for row in rows] == [
        "data/auto_invest.db",
        "data/forward_globalfixed.db",
        "data/forward_wide.db",
        "data/forward_multiasset.db",
    ]
    assert all(row.history_root.startswith(CANDIDATE_RESULT_HISTORY_ROOT) for row in rows)


def test_portfolio_lookup_returns_manifest_history_root() -> None:
    dataset = history_dataset_for_portfolio("deploy/global-trend-wide-portfolio.toml")
    assert dataset is not None
    assert dataset.key == "global-trend-wide"
    assert (
        require_history_root_for_portfolio("deploy/multi-asset-trend-portfolio.toml")
        == "/tmp/candidate_result_history/multi-asset-trend/hist"
    )
    assert (
        require_history_root_for_portfolio("deploy/global-trend-fixed-portfolio.toml")
        == "/tmp/candidate_result_history/global-trend-fixed/hist"
    )


def test_manifest_probe_outputs_tsv_and_json(capsys) -> None:
    assert probe_main(["--manifest"]) == 0
    text = capsys.readouterr().out
    assert text.splitlines()[0] == (
        "micro-gtaa\tdeploy/micro-gtaa-live-portfolio.toml\t"
        "data/auto_invest.db\t/tmp/candidate_result_history/micro-gtaa/hist"
    )

    assert probe_main(["--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload == manifest_document()
