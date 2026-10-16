"""Public Markdown must remain parseable without exposing structured secrets."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

from auto_invest.analytics.money_gate_alignment import _header_json_dict

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/redact_public_sidecar.py"
SPEC = importlib.util.spec_from_file_location("sidecar_markdown_redactor", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
REDACTOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REDACTOR)


def _document(payload):
    return "## 결정 JSON\n```json\n" + json.dumps(payload) + "\n```\n"


def _process(tmp_path, text):
    path = tmp_path / "LAST_RUN.md"
    path.write_text(text, encoding="utf-8")
    REDACTOR._redact_path(path)
    return path.read_text(encoding="utf-8")


def test_decision_numbers_survive_redaction_and_real_consumer(tmp_path):
    payload = {
        "action": "STAY",
        "evidence_age_hours": 1044.123456789012,
        "measurements": [-0.12345678901234, 1.2345678901234e-20, 12345678901234],
        "current_rung": 1,
        "changed": False,
        "missing": None,
    }
    result = _process(tmp_path, _document(payload))
    assert _header_json_dict(result, "결정 JSON") == payload
    assert _process(tmp_path, result) == result


@pytest.mark.parametrize(
    "key",
    ["account_no", "AccountNumber", "access_token", "AppSecret", "kis_order_id",
     "target_capital_usd", "cash_usd", "host", "AccountNavUsd", "account_nav_usd"],
)
@pytest.mark.parametrize("value", [1234567801, {"nested": ["private-value", 1234567801]}])
def test_sensitive_fields_are_masked_at_any_depth(tmp_path, key, value):
    result = _process(tmp_path, _document({"nested": [{key: value}]}))
    assert _header_json_dict(result, "결정 JSON") == {"nested": [{key: "[REDACTED]"}]}
    assert "1234567801" not in result
    assert "private-value" not in result


def test_strings_and_surrounding_prose_keep_existing_masks(tmp_path):
    candidate = "exploratory-price-overlay-12345678901234"
    raw = (
        "KIS_APP_SECRET=outside-secret\n| nav_usd | 12345.67 |\n"
        + _document({"candidate_id": candidate,
                     "note": "account 1234567801 host 203.0.113.10 TOKEN=inside-secret"})
        + "\naccount_no=7654321001\n"
    )
    result = _process(tmp_path, raw)
    payload = _header_json_dict(result, "결정 JSON")
    assert payload["candidate_id"] == candidate
    for secret in ("outside-secret", "12345.67", "1234567801", "203.0.113.10",
                   "inside-secret", "7654321001"):
        assert secret not in result


@pytest.mark.parametrize("opening,closing", [
    ("```json", "```"), ("``` JSON  ", "````"),
    ("  ````json", " `````"), ("~~~json", "~~~~"),
])
def test_fence_forms_multiple_blocks_and_no_final_newline(tmp_path, opening, closing):
    body = json.dumps({"value": 0.12345678901234, "account_no": "1234567801"})
    block = opening + "\n" + body + "\n" + closing
    result = _process(tmp_path, block + "\n\n" + block)
    assert result.count('"value": 0.12345678901234') == 2
    assert result.count('"account_no": "[REDACTED]"') == 2
    assert _process(tmp_path, result) == result


def test_scalar_array_and_crlf_stdin():
    raw = '```json\r\n[0.12345678901234, "1234567801", true, null]\r\n```\r\n'
    completed = subprocess.run([sys.executable, str(SCRIPT)], input=raw,
                               capture_output=True, text=True, check=False)
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout.split("\n", 1)[1].rsplit("```", 1)[0])
    assert payload == [0.12345678901234, "[REDACTED_ACCOUNT]", True, None]


@pytest.mark.parametrize("raw", [
    '```json\n{"evidence_age_hours":1044.[REDACTED_ACCOUNT]}\n```\n',
    '```json\n{"value": nope, "account_no":"1234567801"}\n```\n',
    '```json\n{"value":0.12345678901234,"account_no":"1234567801"}\n',
    '````text\n```json\n{"value":0.12345678901234}\n```\n````\n',
])
def test_invalid_unclosed_and_nested_examples_keep_text_policy(tmp_path, raw):
    assert _process(tmp_path, raw) == REDACTOR.redact(raw)


def test_non_json_code_does_not_hide_following_real_json(tmp_path):
    raw = '```text\naccount_no=1234567801\n```\n' + _document({"value": 0.12345678901234})
    result = _process(tmp_path, raw)
    assert "1234567801" not in result
    assert _header_json_dict(result, "결정 JSON") == {"value": 0.12345678901234}


def test_directory_cli_preserves_json_jsonl_and_git_exclusion(tmp_path):
    payload = {"value": 0.12345678901234, "account_nav_usd": 12345.67}
    expected = {"value": payload["value"], "account_nav_usd": "[REDACTED]"}
    (tmp_path / "LAST_RUN.md").write_text(_document(payload))
    for name in ("evidence.json", "ledger.jsonl"):
        (tmp_path / name).write_text(json.dumps(payload) + "\n")
    (tmp_path / ".git").mkdir()
    ignored = tmp_path / ".git/config"
    ignored.write_text("account_no=1234567801")
    completed = subprocess.run([sys.executable, str(SCRIPT), str(tmp_path)],
                               capture_output=True, text=True, check=False)
    assert completed.returncode == 0, completed.stderr
    assert _header_json_dict((tmp_path / "LAST_RUN.md").read_text(), "결정 JSON") == expected
    for name in ("evidence.json", "ledger.jsonl"):
        assert json.loads((tmp_path / name).read_text()) == expected
    assert ignored.read_text() == "account_no=1234567801"
