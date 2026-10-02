"""One sealed development hypothesis; no broker, authority, or live promotion."""

from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CONTRACT = ROOT / 'specs/206-volume-priority-research/contracts/preregistration.json'
CONTRACT_SHA256 = '0eb8c1b04bacb8e347f0fc1708d7b392cb37b8526ffe6b18a57d388716546a85'


def read_contract():
    raw = CONTRACT.read_bytes()
    if hashlib.sha256(raw).hexdigest() != CONTRACT_SHA256:
        raise ValueError('volume-priority contract changed')
    return json.loads(raw)


def rank_ready_signals(rows, as_of: datetime):
    """Rank one observable decision batch, never signals from later clocks."""
    if (not isinstance(as_of, datetime) or as_of.tzinfo is None
            or as_of.utcoffset() != timedelta(0) or as_of.second or as_of.microsecond):
        raise ValueError('priority requires a UTC decision minute')
    output, seen = [], set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('invalid ready signal')
        symbol, volume = row.get('symbol'), row.get('relative_volume')
        if (not isinstance(symbol, str) or re.fullmatch(r'[A-Z][A-Z0-9.]{0,9}', symbol) is None
                or symbol in seen or type(volume) not in (int, float)
                or not math.isfinite(volume) or volume < 2):
            raise ValueError('invalid priority identity or volume')
        try:
            decision = datetime.fromisoformat(row['decision_at'])
        except (KeyError, TypeError, ValueError):
            raise ValueError('invalid priority decision time') from None
        if decision.tzinfo is None or decision.utcoffset() != timedelta(0) or decision != as_of:
            raise ValueError('priority batch mixes decision times')
        seen.add(symbol)
        output.append(dict(row))
    return sorted(output, key=lambda row: (-row['relative_volume'], row['symbol']))


def replay_volume_priority(inputs, event_sinks=None):
    """Inputs must come from the unchanged sealed 194 input snapshot loader."""
    from auto_invest.analytics.sparse_opening_research import (
        _replay_research,
        sealed_contract,
    )

    contract = read_contract()
    if not isinstance(inputs, dict) or inputs.get('manifest_sha256') != (
            contract['input_manifest_sha256']):
        raise ValueError('volume-priority input identity mismatch')
    parent, _ = sealed_contract(ROOT / 'specs/194-sparse-opening-research/contracts')
    if inputs.get('contract') != parent:
        raise ValueError('volume-priority parent rules mismatch')
    result = _replay_research(inputs, event_sinks, relative_volume_priority=True)
    result.update(
        family_id=contract['family_id'], candidate_count=1,
        minimum_prior_trials=contract['minimum_prior_trials'],
        minimum_total_trials=contract['minimum_total_trials'],
        contract_sha256=CONTRACT_SHA256,
        parent_contract_sha256=contract['parent_contract_sha256'],
        manifest_sha256=contract['input_manifest_sha256'],
        holdout_read=False,
    )
    return result
