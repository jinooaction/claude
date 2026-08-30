from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _write_fixture(tmp_path: Path, candidate_ids: tuple[str, ...]) -> tuple[Path, Path, Path]:
    strategy = tmp_path / "strategy.json"
    audit = tmp_path / "audit.jsonl"
    ledger = tmp_path / "ledger.jsonl"
    rows = [
        {
            "candidate_id": candidate_id,
            "strategy_fingerprint": f"sha256:{index:064x}",
            "family_id": "test-family",
        }
        for index, candidate_id in enumerate(candidate_ids, 1)
    ]
    strategy.write_text(
        json.dumps(
            {
                "global_audit_trial_count": len(candidate_ids),
                "program_research_family_count": 1,
                "audit_records": rows,
            }
        ),
        encoding="utf-8",
    )
    audit.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    ledger.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    return strategy, audit, ledger


def _run(strategy: Path, audit: Path, ledger: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "scripts/validate_public_factory_sidecar.py",
            "--strategy-json",
            str(strategy),
            "--audit-catalog",
            str(audit),
            "--trial-ledger",
            str(ledger),
        ],
        check=False,
        capture_output=True,
        text=True,
    )


def test_public_factory_sidecar_validator_accepts_unique_identity(tmp_path: Path) -> None:
    strategy, audit, ledger = _write_fixture(tmp_path, ("candidate-a", "candidate-b"))

    result = _run(strategy, audit, ledger)

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "audit_rows": 2,
        "ledger_rows": 2,
        "research_families": 1,
        "unique_candidate_ids": 2,
        "unique_strategy_fingerprints": 2,
    }


def test_public_factory_sidecar_validator_rejects_collapsed_candidate_ids(
    tmp_path: Path,
) -> None:
    strategy, audit, ledger = _write_fixture(tmp_path, ("candidate-a", "candidate-a"))

    result = _run(strategy, audit, ledger)

    assert result.returncode == 2
    assert "candidate_id values are not unique" in result.stderr
