"""Spec 111 — design 배포 경계와 후보 파일 저장 단위 검증.

본 파일에서는:
  - write_auto_rules_file이 timestamp 포함 파일명으로 저장.
  - 과거 호환 이름인 prompt_operator_ok/start_live_worker가 즉시 live 경계 오류를 냄.
"""

from __future__ import annotations

import json

import pytest

from auto_invest.design import deploy

# ---------------------------------------------------------- write_auto_rules_file


def test_write_auto_rules_file_creates_timestamped_file(tmp_path):
    cfg_dir = tmp_path / "config"
    path = deploy.write_auto_rules_file("[caps]\nper_trade_pct = 5\n", config_dir=cfg_dir)
    assert path.exists()
    assert path.parent == cfg_dir
    assert path.name.startswith("rules_auto_")
    assert path.name.endswith(".toml")
    assert "[caps]" in path.read_text(encoding="utf-8")


def test_write_proposal_report_creates_adjacent_json(tmp_path):
    rules_path = deploy.write_auto_rules_file("[caps]\n", config_dir=tmp_path)
    report_path = deploy.write_proposal_report(
        {
            "authority": "PROPOSAL_ONLY",
            "candidate_fingerprint": "abc",
            "verification": {"ok": False, "overall_status": "WAIT_DYNAMIC_VALIDATION"},
        },
        rules_path=rules_path,
    )

    assert report_path == rules_path.with_suffix(".proposal.json")
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["authority"] == "PROPOSAL_ONLY"
    assert payload["verification"]["ok"] is False


# ---------------------------------------------------------- live boundary compatibility


def test_prompt_operator_ok_is_no_longer_live_authority() -> None:
    with pytest.raises(deploy.LiveActivationBoundaryError):
        deploy.prompt_operator_ok()


def test_start_live_worker_is_no_longer_live_authority() -> None:
    with pytest.raises(deploy.LiveActivationBoundaryError):
        deploy.start_live_worker()
