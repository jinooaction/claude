from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from auto_invest.cli import app

runner = CliRunner()


def test_rejected_order_opportunity_cli_uses_marks_json(tmp_path: Path) -> None:
    result_json = tmp_path / "micro_live.json"
    marks_json = tmp_path / "marks.json"
    result_json.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "symbol": "IEF",
                        "side": "BUY",
                        "requested_qty": 3,
                        "routed_qty": 3,
                        "limit_price_usd": "95.08",
                        "state": "REJECTED_BY_BROKER",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    marks_json.write_text(json.dumps({"IEF": "94.79"}), encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "rejected-order-opportunity",
            "--result-json",
            str(result_json),
            "--marks-json",
            str(marks_json),
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["rejected_count"] == 1
    assert payload["valued_count"] == 1
    assert payload["total_opportunity_pnl_usd"] == "-0.87"
    assert payload["rows"][0]["symbol"] == "IEF"


def test_rejected_order_opportunity_cli_text_without_marks_is_nonfatal(
    tmp_path: Path,
) -> None:
    result_json = tmp_path / "micro_live.json"
    result_json.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "symbol": "SPYM",
                        "side": "BUY",
                        "requested_qty": 3,
                        "routed_qty": 3,
                        "limit_price_usd": "86.49",
                        "state": "REJECTED_BY_BROKER",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "rejected-order-opportunity",
            "--result-json",
            str(result_json),
            "--format",
            "text",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "거부 주문 기회손익" in result.stdout
    assert "현재가 조회 오류: no marks source provided" in result.stdout
    assert "현재가 없음: SPYM" in result.stdout
