"""Acquire available KIS history for five ETFs and assess it without broker orders."""

import json
import subprocess
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from auto_invest.analytics.intraday_paper_challenger import (
    build_candidate_registry,
    load_intraday_dataset,
    load_preregistration,
    render_intraday_markdown,
    resample_dataset,
    run_intraday_paper_challenger,
    simulate_candidate,
)
from auto_invest.analytics.intraday_paper_challenger_evidence import assess_intraday_evidence
from auto_invest.market_data.intraday import (
    CALENDAR,
    NY,
    SYMBOLS,
    DataError,
    digest,
    iso,
    utc,
    write_batch,
)
from auto_invest.market_data.kis_history_depth import _save, probe_kis_history_depth

ROOT = Path(__file__).resolve().parents[3]
PREREG = ROOT / "specs/177-intraday-paper-challenger/contracts/intraday-preregistration.json"


def _diagnostic(dataset, config):
    """Short-window replay only. Never a substitute for independent holdout evidence."""
    result = dict(status="DATA_INCOMPLETE", observation_type="SHORT_WINDOW_DIAGNOSTIC",
                  session_count=len(dataset.sessions), promotion_eligible=False, runs=[])
    if dataset.quality_reasons or not dataset.sessions:
        return result
    registry = build_candidate_registry(config)
    cache = {t: resample_dataset(dataset, t) for t in {c.timeframe_minutes for c in registry}}
    for candidate in registry:
        for model in ("base", "stress"):
            run = simulate_candidate(
                candidate, cache[candidate.timeframe_minutes], dataset.sessions,
                config, cost_model_name=model,
            )
            result["runs"].append(dict(
                candidate_id=candidate.candidate_id, cost_model=model,
                net_pnl_usd=run.total_net_pnl_usd, cost_usd=run.total_cost_usd,
                closed_trades=len(run.trade_records), unclosed_quantity=run.unclosed_quantity,
                daily_pnl_usd={str(k): v for k, v in run.daily_pnl_usd.items()},
                ledger_rows=list(run.ledger_rows),
            ))
    result["status"] = "REPLAYED"
    return result


async def acquire_kis_history_review(transport, env, cache_path, output_root, *, now=None):
    started = now or datetime.now(UTC)
    if started.utcoffset() is None:
        raise DataError("HISTORY_TIME_INVALID")
    root = Path(output_root)
    if root.is_symlink():
        raise DataError("HISTORY_OUTPUT_LINK")
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    if root.stat().st_mode & 0o077:
        raise DataError("HISTORY_PRIVATE_OUTPUT_REQUIRED")
    run = root / ("review-" + uuid4().hex)
    run.mkdir(mode=0o700)
    prereg = PREREG.read_bytes()
    summaries, by_symbol, ranges = [], {}, []
    for symbol in SYMBOLS:
        result = await probe_kis_history_depth(transport, env, cache_path, run / "sources",
                                               symbol=symbol)
        source = Path(result["source_path"]) / "regular-bars.json"
        rows = json.loads(source.read_bytes())
        closed = []
        for row in rows:
            if row["symbol"] != symbol:
                raise DataError("HISTORY_SOURCE_SYMBOL")
            day = utc(row["timestamp_utc"]).astimezone(NY).date()
            if CALENDAR.session_close(day).to_pydatetime() <= started:
                closed.append(row)
        if not closed:
            raise DataError("HISTORY_NO_CLOSED_DATA")
        days = {utc(r["timestamp_utc"]).astimezone(NY).date() for r in closed}
        ranges.append((min(days), max(days)))
        by_symbol[symbol] = closed
        summaries.append({k: v for k, v in result.items() if k != "page_digests"} |
                         dict(regular_source_sha256=digest(source.read_bytes())))
    first, last = max(r[0] for r in ranges), min(r[1] for r in ranges)
    if first > last:
        raise DataError("HISTORY_NO_COMMON_RANGE")
    rows = [row for symbol in SYMBOLS for row in by_symbol[symbol]
            if first <= utc(row["timestamp_utc"]).astimezone(NY).date() <= last]
    rows.sort(key=lambda r: (r["timestamp_utc"], r["symbol"]))
    observed = iso(datetime.now(UTC))
    write_batch(run / "dataset", dict(
        provider="kis-nasdaq-partial-unadjusted", synthetic=False,
        retrieved_at_utc=observed, pages=[], bars=rows, source_runs=summaries,
    ))
    config = load_preregistration(PREREG)
    if PREREG.read_bytes() != prereg:
        raise DataError("HISTORY_PREREGISTRATION_CHANGED")
    dataset = load_intraday_dataset(run / "dataset", run / "dataset/manifest.json", config)
    expected = {d.date() for d in CALENDAR.sessions_in_range(first, last)}
    missing = expected - set(dataset.sessions)
    if missing:
        dataset = replace(dataset, quality_reasons=dataset.quality_reasons + (
            "history_common_calendar_incomplete",
        ))
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    report, ledger = run_intraday_paper_challenger(
        dataset, config, preregistration_bytes=prereg, code_commit=commit,
        generated_at_utc=observed,
    )
    evidence = assess_intraday_evidence(report, config, preregistration_bytes=prereg,
                                        ledger_bytes=ledger)
    if not evidence.valid:
        raise DataError("HISTORY_INDEPENDENT_REVIEW_FAILED")
    diagnostic = _diagnostic(dataset, config)
    _save(run / "short-window-diagnostic.json", diagnostic, ())
    _save(run / "research.json", report, ())
    (run / "ledger.csv").write_bytes(ledger)
    (run / "summary.md").write_text(render_intraday_markdown(report))
    result = dict(
        status="HISTORY_REVIEWED", sources=summaries, first_common_date=str(first),
        last_common_date=str(last), expected_sessions=len(expected),
        complete_sessions=len(dataset.sessions), missing_calendar_sessions=len(missing),
        required_sessions=config["minimum_evidence"]["minimum_total_sessions"],
        decision=report["decision"], independent_evidence_valid=True, source_path=str(run),
        short_window_diagnostic=dict(status=diagnostic["status"], runs=len(diagnostic["runs"]),
                                     promotion_eligible=False),
        orders_submitted=0, live_eligible=False,
    )
    _save(run / "completed.json", result, ())
    return result
