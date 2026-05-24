"""Spec 004 T021 [US2] — daily_summary 판단 지점 + 리포트 통합.

성공 시 서술 요약, LLM 실패 시 결정론적 폴백(카운터만). 둘 다 리포트는 정상.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from auto_invest.judgment.client import JudgmentClient
from auto_invest.judgment.points.daily_summary import (
    attach_summary_to_report,
    fallback_narrative,
    summarize_day,
)
from auto_invest.persistence import audit, db
from auto_invest.reports.daily import DailyReport, render_json, render_markdown
from auto_invest.telemetry.prices import load_prices

_COUNTERS = {"orders_attempted": 7, "fills": 3, "orders_rejected_by_gate": 2, "errors": 0}
_RESPONSE = (
    '{"narrative": "조용한 하루: 7건 시도 중 3건 체결, 2건 게이트 거부.", '
    '"alerts": ["게이트 거부율 다소 높음"]}'
)


class _Block:
    def __init__(self, text: str) -> None:
        self.text = text


class _Response:
    def __init__(self) -> None:
        self.content = [_Block(_RESPONSE)]
        self.model = "claude-sonnet-4-6"
        self.usage = {
            "input_tokens": 200,
            "output_tokens": 80,
            "cache_read_input_tokens": 0,
            "cache_creation_input_tokens": 0,
        }


class _OkMessages:
    async def create(self, **kwargs: Any):
        return _Response()


class _FailMessages:
    async def create(self, **kwargs: Any):
        raise RuntimeError("anthropic down")


class _Client:
    def __init__(self, messages) -> None:
        self.messages = messages


@pytest.fixture
def conn(tmp_path: Path):
    c = db.get_connection(tmp_path / "t.db")
    db.migrate(c)
    yield c
    c.close()


@pytest.fixture
def prices():
    return load_prices(Path("config/llm_prices.toml"))


@pytest.mark.asyncio
async def test_summary_success_returns_narrative(conn, prices):
    jc = JudgmentClient(_Client(_OkMessages()), conn=conn, prices=prices)
    summary = await summarize_day(jc, conn=conn, counters=_COUNTERS)
    assert "조용한 하루" in summary
    assert "경보:" in summary
    # token_usage + LLM_CALL 기록됨
    assert conn.execute("SELECT COUNT(*) c FROM token_usage").fetchone()["c"] == 1


@pytest.mark.asyncio
async def test_summary_failure_falls_back_to_counters(conn, prices):
    jc = JudgmentClient(_Client(_FailMessages()), conn=conn, prices=prices)
    summary = await summarize_day(jc, conn=conn, counters=_COUNTERS)
    assert "생성 불가" in summary
    assert "주문 시도 7" in summary
    # 폴백 감사 기록
    fb = [r for r in audit.read_all(conn) if r["event_type"] == "JUDGMENT_FALLBACK"]
    assert fb and "failure" in fb[0]["payload_json"]


def test_fallback_narrative_is_deterministic():
    assert fallback_narrative(_COUNTERS) == fallback_narrative(_COUNTERS)
    assert "주문 시도 7" in fallback_narrative(_COUNTERS)


def _bare_report() -> DailyReport:
    return DailyReport(
        session_date="2026-05-24",
        generated_at="2026-05-24T20:00:00Z",
        counters=_COUNTERS,
        rules=[],
        rejections=[],
        positions=[],
        reconciliation="OK",
    )


def test_report_renders_judgment_section_when_present():
    rep = attach_summary_to_report(_bare_report(), "오늘 요약 본문")
    md = render_markdown(rep)
    assert "## Judgment Summary (daily_summary)" in md
    assert "오늘 요약 본문" in md
    import json as _json

    assert _json.loads(render_json(rep))["judgment_summary"] == "오늘 요약 본문"


def test_report_omits_section_when_absent():
    md = render_markdown(_bare_report())
    assert "Judgment Summary" not in md
