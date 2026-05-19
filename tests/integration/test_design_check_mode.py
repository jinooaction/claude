"""Spec 010 후속 PR — `auto-invest design --check` 모드 통합 검증.

`--check`는 가장 최근 RULE_DESIGN_DEPLOYED의 라이브 worker 상태를 한글로 요약.
intent 입력 없어도 됨. read-only — DB 무수정.
"""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from auto_invest.cli import app
from auto_invest.persistence import audit, db
from auto_invest.persistence.audit import (
    FillPayload,
    OrderIntentPayload,
    OrderRejectedByGatePayload,
    RuleDesignCompletedPayload,
    RuleDesignDeployedPayload,
    RuleDesignRequestedPayload,
    WorkerStartedPayload,
)


@pytest.fixture
def runner():
    return CliRunner()


def test_check_no_db_file_returns_friendly_message(runner, tmp_path):
    """edge case — DB 파일이 없으면 한글 안내 + exit 0."""
    result = runner.invoke(
        app,
        ["design", "--check", "--db", str(tmp_path / "missing.db")],
    )
    assert result.exit_code == 0
    assert "DB 파일이 없습니다" in result.stdout


def test_check_no_deployed_returns_friendly_message(runner, tmp_path):
    """audit_log에 RULE_DESIGN_DEPLOYED row 없으면 한글 안내."""
    db_path = tmp_path / "auto.db"
    conn = db.get_connection(db_path)
    db.migrate(conn)
    conn.close()

    result = runner.invoke(app, ["design", "--check", "--db", str(db_path)])
    assert result.exit_code == 0
    assert "아직 라이브로 배포된" in result.stdout


def test_check_summary_with_live_stats(runner, tmp_path):
    """RULE_DESIGN_DEPLOYED + 라이브 worker 통계가 정확히 한글 요약."""
    db_path = tmp_path / "auto.db"
    conn = db.get_connection(db_path)
    db.migrate(conn)

    # 1. RULE_DESIGN_REQUESTED seed.
    design_session_id = audit.append(
        conn,
        RuleDesignRequestedPayload(
            intent="자본 100달러, 미국 대형주, 위험 보통",
            requested_at_utc="2026-05-19T01:00:00.000Z",
            kis_balance_usd="102.45",
            kis_holdings=[],
            host="h",
        ),
    )

    # 2. RULE_DESIGN_COMPLETED (interpretation 포함).
    audit.append(
        conn,
        RuleDesignCompletedPayload(
            intent="자본 100달러, 미국 대형주, 위험 보통",
            interpretation={"max_drawdown_pct": 5, "universe": ["VOO"]},
            generated_rules_toml="[caps]\nper_trade_pct = 5\n",
            model_id="claude-opus-4-7",
            tokens_input=100,
            tokens_output=50,
            cost_usd="0.01",
            retry_index=1,
        ),
    )

    # 3. WORKER_STARTED (라이브 worker).
    live_session_id = audit.append(
        conn,
        WorkerStartedPayload(pid=12345, config_path="/x"),
    )

    # 4. RULE_DESIGN_DEPLOYED.
    audit.append(
        conn,
        RuleDesignDeployedPayload(
            design_session_id=design_session_id,
            live_session_id=live_session_id,
            deployed_at_utc="2026-05-19T02:00:00.000Z",
            total_capital_usd="100.00",
        ),
    )

    # 5. 라이브 worker 시작 이후 통계 — 시그널 3건, 체결 2건, 차단 1건.
    for i in range(3):
        audit.append(
            conn,
            OrderIntentPayload(
                rule_id="r",
                symbol="VOO",
                side="BUY",
                order_type="MARKET",
                qty=1,
                limit_price_usd=None,
            ),
            rule_id="r",
            correlation_id=f"c{i}",
        )
    for i in range(2):
        audit.append(
            conn,
            FillPayload(
                kis_fill_id=f"k{i}",
                qty=1,
                price_usd="100.00",
                executed_at_utc="2026-05-19T03:00:00.000Z",
            ),
        )
    audit.append(
        conn,
        OrderRejectedByGatePayload(
            gate="per_trade_cap_gate",
            reason="exceeds cap",
            metadata={},
        ),
    )

    conn.close()

    result = runner.invoke(app, ["design", "--check", "--db", str(db_path)])
    assert result.exit_code == 0, f"--check exit code 0 기대, stdout={result.stdout}"
    out = result.stdout
    # 핵심 요약 항목 모두 표시.
    assert "auto-invest design --check" in out
    assert f"design session: seq={design_session_id}" in out
    assert f"라이브 worker: seq={live_session_id}" in out
    assert "실행 중" in out  # WORKER_STOPPED row 없음
    assert "자본 100달러" in out  # 운영자 의도
    assert "max_drawdown_pct" in out  # Claude 해석
    assert "ORDER_INTENT" in out
    # 카운트가 정확.
    assert " 3" in out  # signals
    assert " 2" in out  # fills
    assert " 1" in out  # denied
    assert " 0" in out  # errors


def test_check_marks_worker_stopped(runner, tmp_path):
    """WORKER_STOPPED 있으면 '종료됨'으로 표시."""
    from auto_invest.persistence.audit import WorkerStoppedPayload

    db_path = tmp_path / "auto.db"
    conn = db.get_connection(db_path)
    db.migrate(conn)

    design_session_id = audit.append(
        conn,
        RuleDesignRequestedPayload(
            intent="x",
            requested_at_utc="2026-05-19T01:00:00.000Z",
            kis_balance_usd="100",
            kis_holdings=[],
            host="h",
        ),
    )
    live_session_id = audit.append(
        conn,
        WorkerStartedPayload(pid=1, config_path="/x"),
    )
    audit.append(
        conn,
        RuleDesignDeployedPayload(
            design_session_id=design_session_id,
            live_session_id=live_session_id,
            deployed_at_utc="2026-05-19T02:00:00.000Z",
            total_capital_usd="100",
        ),
    )
    audit.append(conn, WorkerStoppedPayload(reason="normal_shutdown"))
    conn.close()

    result = runner.invoke(app, ["design", "--check", "--db", str(db_path)])
    assert result.exit_code == 0
    assert "종료됨" in result.stdout


def test_check_is_read_only(runner, tmp_path):
    """--check 모드는 audit_log에 단 1줄도 INSERT하지 않아야 함."""
    db_path = tmp_path / "auto.db"
    conn = db.get_connection(db_path)
    db.migrate(conn)
    audit.append(
        conn,
        RuleDesignRequestedPayload(
            intent="x",
            requested_at_utc="2026-05-19T01:00:00.000Z",
            kis_balance_usd="100",
            kis_holdings=[],
            host="h",
        ),
    )
    before_count = conn.execute(
        "SELECT COUNT(*) AS n FROM audit_log"
    ).fetchone()["n"]
    conn.close()

    result = runner.invoke(app, ["design", "--check", "--db", str(db_path)])
    assert result.exit_code == 0

    conn = db.get_connection(db_path)
    after_count = conn.execute(
        "SELECT COUNT(*) AS n FROM audit_log"
    ).fetchone()["n"]
    conn.close()

    assert before_count == after_count
