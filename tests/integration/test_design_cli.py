"""Spec 010 통합 테스트 — design CLI 진입점.

본 PR에서 검증 가능한 SC:
- SC-007 (mutex 거부 → exit 70).

KIS 잔고 조회·Claude 호출 mock이 필요한 end-to-end는 후속 PR에서 더
확장한다 (T018 등). 본 통합 테스트는 design CLI의 mutex 단계까지를 검증.
"""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from auto_invest.cli import app
from auto_invest.persistence import audit, db
from auto_invest.persistence.audit import RuleDesignRequestedPayload


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def workspace(tmp_path):
    """design 명령에 필요한 최소 파일 — env + prices."""
    env_file = tmp_path / ".env"
    env_file.write_text(
        "KIS_APP_KEY=test-key\n"
        "KIS_APP_SECRET=test-secret\n"
        "KIS_ACCOUNT_NO=1234567801\n"
        "ANTHROPIC_API_KEY=test-anth-key\n"
    )
    prices_toml = tmp_path / "prices.toml"
    prices_toml.write_text(
        """
[claude-opus-4-7]
usd_per_million_input_tokens = 15
usd_per_million_output_tokens = 75
usd_per_million_cache_write_tokens = 18.75
usd_per_million_cache_read_tokens = 1.5
""".strip()
    )

    db_path = tmp_path / "auto_invest.db"
    conn = db.get_connection(db_path)
    db.migrate(conn)
    conn.close()

    return {
        "env": env_file,
        "prices": prices_toml,
        "db": db_path,
    }


def test_us1_mutex_rejection(runner, workspace):
    """SC-007 — 이미 떠 있는 design 명령 있으면 새 호출은 exit 70."""
    db_path = workspace["db"]
    conn = db.get_connection(db_path)
    audit.append(
        conn,
        RuleDesignRequestedPayload(
            intent="이미 떠있음",
            requested_at_utc="2026-05-19T01:00:00.000Z",
            kis_balance_usd="100",
            kis_holdings=[],
            host="h",
        ),
    )
    conn.close()

    result = runner.invoke(
        app,
        [
            "design",
            "--intent", "자본 100달러, 미국 대형주 분산",
            "--db", str(db_path),
            "--env-file", str(workspace["env"]),
            "--prices", str(workspace["prices"]),
        ],
    )

    assert result.exit_code == 70, (
        f"mutex 충돌 시 exit 70 기대, 실제 {result.exit_code}\n"
        f"stdout: {result.stdout}"
    )

    # PAPER_RUN_REJECTED가 아닌 RULE_DESIGN_REJECTED audit row.
    conn = db.get_connection(db_path)
    rows = list(conn.execute(
        "SELECT payload_json FROM audit_log "
        "WHERE event_type = 'RULE_DESIGN_REJECTED'"
    ))
    conn.close()
    assert len(rows) == 1
    import json
    payload = json.loads(rows[0]["payload_json"])
    assert payload["reason"] == "mutex_conflict"


def test_us1_empty_intent_rejected(runner, workspace):
    """edge case 1 — 빈 의도 → exit 2."""
    result = runner.invoke(
        app,
        [
            "design",
            "--intent", "",
            "--db", str(workspace["db"]),
            "--env-file", str(workspace["env"]),
            "--prices", str(workspace["prices"]),
        ],
    )
    assert result.exit_code == 2
