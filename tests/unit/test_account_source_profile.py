import json

import pytest

from auto_invest.broker.account_source_profile import (
    CASH_FIELDS,
    FIELDS,
    MARGIN_URL,
    profile_margin_responses,
)


def record(rows):
    return dict(endpoint=MARGIN_URL, http_status=200, data=dict(rt_cd="0", output=rows))


def row(currency="USD", **changes):
    return dict(dict.fromkeys(FIELDS, "0"), crcy_cd=currency, **changes)


def test_duplicates_zero_rows_and_unclassified_values_are_described_not_aggregated():
    money = row(natn_name="PRIVATE_NATION", private_field="PRIVATE_ACCOUNT")
    money["frcr_dncl_amt1"] = "987654.32109"
    result = profile_margin_responses([record([
        row(), money, dict(money, natn_name="ANOTHER_PRIVATE_NATION"),
        row("EUR"), row(" "), row("bad-code", ustl_buy_amt="unknown"),
    ])])
    usd = result["responses"][0]["USD"]
    assert usd["row_count"] == 3
    assert usd["cash_vector_complete_count"] == 3
    assert usd["cash_vector_zero_count"] == 1
    assert usd["cash_vector_distinct_count"] == 2
    assert usd["country_name_distinct_count"] == 2
    assert usd["fields"]["frcr_dncl_amt1"] == dict(
        valid_count=3, invalid_or_missing_count=0, zero_count=1, negative_count=0, distinct_count=2,
    )
    unknown = result["responses"][0]["UNCLASSIFIED"]
    assert unknown["row_count"] == 2 and unknown["cash_vector_complete_count"] == 1
    assert unknown["cash_vector_zero_count"] == 1
    assert result["responses"][0]["OTHER_CURRENCY"]["row_count"] == 1
    assert result["cash_aggregation_verified"] is result["live_eligible"] is False
    rendered = json.dumps(result)
    for secret in ("987654.32109", "PRIVATE", "private_field", "bad-code", "EUR", "unknown"):
        assert secret not in rendered


@pytest.mark.parametrize("value", [None, "", "NaN", "Infinity", "1e3", True, 0, "1,000", "9" * 19])
def test_missing_or_invalid_amount_never_becomes_zero(value):
    item = row()
    item[CASH_FIELDS[0]] = value
    result = profile_margin_responses([record([item])])["responses"][0]["USD"]
    assert result["cash_vector_complete_count"] == result["cash_vector_zero_count"] == 0
    assert result["fields"][CASH_FIELDS[0]]["invalid_or_missing_count"] == 1


def test_numeric_equivalence_and_negative_amounts_do_not_change_source_rows():
    items = [row(), row()]
    items[0][CASH_FIELDS[0]] = " -12.50 "
    items[1][CASH_FIELDS[0]] = "-12.500"
    before = json.dumps(items)
    profile = profile_margin_responses([record(items)])
    group = profile["responses"][0]["USD"]
    assert group["cash_vector_distinct_count"] == 1
    assert group["fields"][CASH_FIELDS[0]]["negative_count"] == 2
    assert json.dumps(items) == before


def test_repeated_snapshots_and_pages_are_not_summed_or_deduplicated():
    response = record([row()])
    result = profile_margin_responses([response, response])
    assert len(result["responses"]) == 2
    assert all(snapshot["USD"]["row_count"] == 1 for snapshot in result["responses"])


@pytest.mark.parametrize("change", [
    {"http_status": 500}, {"data": None}, {"data": {"rt_cd": "1"}},
    {"data": {"rt_cd": "0", "output": [None]}},
    {"data": {"rt_cd": "0", "output": [{}] * 2001}},
])
def test_failed_or_malformed_response_is_not_reported_as_complete(change):
    bad = dict(record([row()]), **change)
    result = profile_margin_responses([bad, record([row()])])
    assert result["status"] == "SOURCE_STRUCTURE_PARTIAL"
    assert result["excluded_response_count"] == 1
    assert len(result["responses"]) == 1


def test_no_matching_source_has_no_structure_claim():
    assert profile_margin_responses([])["status"] == "SOURCE_STRUCTURE_UNAVAILABLE"
    assert profile_margin_responses([record([])] * 201)["responses"] == []
