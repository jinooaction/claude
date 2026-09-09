"""Connect immutable daily archives to the existing broker-free research evaluator."""

import json
import re
from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from auto_invest.analytics.intraday_paper_challenger import (
    load_intraday_dataset,
    load_preregistration,
    run_intraday_paper_challenger,
)
from auto_invest.market_data.intraday import (
    CALENDAR,
    SYMBOLS,
    DataError,
    digest,
    encode,
    iso,
    utc,
    write_batch,
)


def review_archives(archives: Path, output: Path, preregistration: Path, code_commit: str) -> dict:
    """Validate snapshots first; preserve originals and never overwrite a prior review."""
    if not re.fullmatch(r"[0-9a-f]{40}", code_commit):
        raise DataError("ARCHIVE_CODE_IDENTITY")
    if output.exists() or output.is_symlink():
        raise DataError("ARCHIVE_OUTPUT_EXISTS")
    if not archives.is_dir() or archives.is_symlink():
        raise DataError("ARCHIVE_ROOT_INVALID")
    if output.resolve().is_relative_to(archives.resolve()):
        raise DataError("ARCHIVE_OUTPUT_INSIDE_SOURCE")
    folders = sorted(archives.iterdir())
    if not 1 <= len(folders) <= 2000:
        raise DataError("ARCHIVE_COUNT_INVALID")
    config = load_preregistration(preregistration)
    prereg_bytes = preregistration.read_bytes()
    rows, lineage, sessions = [], [], set()
    incomplete_archives = 0
    identity = None
    for folder in folders:
        if not folder.is_dir() or folder.is_symlink():
            raise DataError("ARCHIVE_ENTRY_INVALID")
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}-partial-[0-9a-f]{32}", folder.name):
            incomplete_archives += 1
            continue
        try:
            session = date.fromisoformat(folder.name)
            if session.isoformat() != folder.name or session in sessions:
                raise ValueError
        except ValueError:
            raise DataError("ARCHIVE_SESSION_INVALID") from None
        # Read once, then validate and parse the same bytes in a private snapshot.
        with TemporaryDirectory(prefix="intraday-archive-") as temporary:
            snapshot = Path(temporary)
            for name in ("manifest.json", "source.json", *(f"{s}.csv" for s in SYMBOLS)):
                source = folder / name
                if (not source.is_file() or source.is_symlink()
                        or source.stat().st_size > 50_000_000):
                    raise DataError("ARCHIVE_FILE_INVALID")
                (snapshot / name).write_bytes(source.read_bytes())
            try:
                manifest = json.loads((snapshot / "manifest.json").read_bytes())
                raw = (snapshot / "source.json").read_bytes()
                raw_hash = digest(raw)
                if manifest["raw_sha256"] != raw_hash or manifest["dataset_id"] != raw_hash:
                    raise ValueError
                source_metadata = json.loads(raw)
                if any(source_metadata[k] != manifest[k] for k in ("provider", "synthetic")):
                    raise ValueError
                dataset = load_intraday_dataset(snapshot, snapshot / "manifest.json", config)
                if dataset.provider not in {"alpaca-sip-split", "kis-nasdaq-partial-unadjusted"}:
                    raise ValueError
                policy = ("split; dividends unadjusted" if dataset.provider == "alpaca-sip-split"
                          else "provider unadjusted; partial-market; revisions possible")
                current = (dataset.provider, dataset.synthetic, manifest["adjustment_policy"])
                if current[2] != policy:
                    raise ValueError
            except Exception:
                raise DataError("ARCHIVE_INTEGRITY_INVALID") from None
            if dataset.quality_reasons or dataset.sessions != (session,):
                raise DataError("ARCHIVE_SESSION_INCOMPLETE")
            if identity is not None and current != identity:
                raise DataError("ARCHIVE_SOURCE_MIXED")
            identity = current
            sessions.add(session)
            lineage.append(dict(session=session.isoformat(), raw_sha256=raw_hash,
                                manifest_sha256=digest((snapshot / "manifest.json").read_bytes())))
            daily_rows = []
            for symbol in SYMBOLS:
                for bar in dataset.bars_by_symbol[symbol]:
                    if bar.session_close_utc > utc(manifest["retrieved_at_utc"]):
                        raise DataError("ARCHIVE_NOT_YET_CLOSED")
                    daily_rows.append(dict(timestamp_utc=iso(bar.timestamp_utc), symbol=symbol,
                                           open=bar.open, high=bar.high, low=bar.low,
                                           close=bar.close, volume=bar.volume))
            try:
                def key(row):
                    return row["timestamp_utc"], row["symbol"]

                if sorted(source_metadata["bars"], key=key) != sorted(daily_rows, key=key):
                    raise ValueError
            except Exception:
                raise DataError("ARCHIVE_SOURCE_CSV_DISAGREE") from None
            rows.extend(daily_rows)
    if not sessions:
        raise DataError("ARCHIVE_NO_COMPLETE_SESSIONS")
    now = iso(datetime.now(UTC))
    rows.sort(key=lambda r: (r["timestamp_utc"], r["symbol"]))
    write_batch(output, dict(provider=identity[0], synthetic=identity[1],
                             retrieved_at_utc=now, pages=[], bars=rows, archives=lineage))
    combined = load_intraday_dataset(output, output / "manifest.json", config)
    expected = {s.date() for s in CALENDAR.sessions_in_range(min(sessions), max(sessions))}
    missing_calendar = len(expected - sessions)
    if missing_calendar:
        combined = replace(combined, quality_reasons=combined.quality_reasons
                           + ("archive_calendar_sessions_missing",))
    payload, ledger = run_intraday_paper_challenger(
        combined, config, preregistration_bytes=prereg_bytes,
        code_commit=code_commit, generated_at_utc=now,
    )
    required = config["minimum_evidence"]["minimum_total_sessions"]
    result = dict(
        status="HISTORY_REVIEWED", session_count=len(combined.sessions),
        required_sessions=required, missing_sessions=max(0, required - len(combined.sessions)),
        missing_calendar_sessions=missing_calendar,
        incomplete_archive_count=incomplete_archives,
        provider=combined.provider, synthetic=combined.synthetic,
        dataset_fingerprint=combined.dataset_fingerprint, decision=payload["decision"],
        observation_type="HISTORICAL_RESEARCH", live_eligible=False, orders_submitted=0,
    )
    (output / "research.json").write_bytes(encode(payload))
    (output / "ledger.csv").write_bytes(ledger)
    # A manifest proves a dataset exists, not that evaluation completed.
    marker = output / ".review.tmp"
    marker.write_bytes(encode(result))
    marker.rename(output / "review.json")
    return result
