#!/usr/bin/env python3
"""Run the no-order spec-162 USDA crop supply-demand strategy factory."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime
from pathlib import Path
from urllib.parse import urlparse

from auto_invest.analytics.global_trend import align_gold_levels, parse_gold
from auto_invest.analytics.risk_managed_beta import parse_shiller
from auto_invest.analytics.usda_crop_supply_demand_factory import (
    ESMIS_INDEX_URL,
    WasdeWorkbookRef,
    load_crop_supply_demand_bundle,
    parse_wasde_index_pages,
    render_usda_crop_factory_markdown,
    run_usda_crop_supply_demand_factory,
)
from auto_invest.market_data.public_data import parse_fred_csv

SHILLER_URL = "https://raw.githubusercontent.com/datasets/s-and-p-500/main/data/data.csv"
GOLD_URL = "https://raw.githubusercontent.com/datasets/gold-prices/main/data/monthly.csv"
MAX_INDEX_PAGES = 24


def _read_bytes(path: Path | None, url: str) -> bytes:
    if path is not None:
        return path.read_bytes()
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})  # noqa: S310
    with urllib.request.urlopen(request, timeout=120) as response:  # noqa: S310
        return response.read()


def _index_pages(directory: Path | None) -> list[str]:
    if directory is not None:
        paths = sorted(directory.glob("*.html"))
        if not paths:
            raise ValueError("WASDE index directory has no HTML pages")
        return [path.read_text(encoding="utf-8") for path in paths]
    pages: list[str] = []
    for page in range(MAX_INDEX_PAGES):
        separator = "&" if "?" in ESMIS_INDEX_URL else "?"
        url = f"{ESMIS_INDEX_URL}{separator}page={page}"
        text = _read_bytes(None, url).decode("utf-8")
        pages.append(text)
        if 'datetime="2010-07-' in text:
            break
    return pages


def _workbook_path(directory: Path, ref: WasdeWorkbookRef) -> Path:
    name = Path(urlparse(ref.url).path).name
    return directory / name


def _workbooks(
    refs: tuple[WasdeWorkbookRef, ...],
    directory: Path | None,
) -> dict[str, bytes]:
    if directory is not None:
        return {
            url: _workbook_path(
                directory,
                WasdeWorkbookRef(ref.release_date, url),
            ).read_bytes()
            for ref in refs
            for url in ref.archive_urls
        }

    def fetch(item: tuple[date, str]) -> tuple[str, bytes]:
        _, url = item
        return url, _read_bytes(None, url)

    with ThreadPoolExecutor(max_workers=8) as pool:
        items = [
            (ref.release_date, url)
            for ref in refs
            for url in ref.archive_urls
        ]
        return dict(pool.map(fetch, items))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wasde-index-dir", type=Path)
    parser.add_argument("--wasde-data-dir", type=Path)
    parser.add_argument("--shiller-file", type=Path)
    parser.add_argument("--gold-file", type=Path)
    parser.add_argument("--macro-data-dir", type=Path, required=True)
    parser.add_argument("--prior-factory-json", type=Path, required=True)
    parser.add_argument("--calibration-json", type=Path, required=True)
    parser.add_argument("--controls-json", type=Path, required=True)
    parser.add_argument("--code-commit", default="unknown")
    parser.add_argument("--timestamp-utc")
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--summary-out", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    timestamp = args.timestamp_utc or datetime.now(UTC).isoformat()
    try:
        current_date = datetime.fromisoformat(timestamp.replace("Z", "+00:00")).date()
        refs = parse_wasde_index_pages(_index_pages(args.wasde_index_dir))
        cash_text = (args.macro_data_dir / "fred" / "DGS3MO.csv").read_text(
            encoding="utf-8"
        )
        bundle = load_crop_supply_demand_bundle(
            refs,
            _workbooks(refs, args.wasde_data_dir),
            parse_fred_csv(cash_text),
            current_date=current_date,
        )
        shiller_text = _read_bytes(args.shiller_file, SHILLER_URL).decode()
        shiller_by_month = {row.date[:7]: row for row in parse_shiller(shiller_text)}
        rows = [shiller_by_month[month[:7]] for month in bundle.dates]
        gold_text = _read_bytes(args.gold_file, GOLD_URL).decode()
        gold = align_gold_levels(rows, parse_gold(gold_text))
        prior = json.loads(args.prior_factory_json.read_text(encoding="utf-8"))
        calibration = json.loads(args.calibration_json.read_text(encoding="utf-8"))
        controls = json.loads(args.controls_json.read_text(encoding="utf-8"))
        payload = run_usda_crop_supply_demand_factory(
            rows,
            gold,
            bundle,
            prior_factory_payload=prior,
            calibration_evidence=calibration,
            full_gate_controls=controls,
            code_commit=args.code_commit,
            timestamp_utc=timestamp,
        )
    except (KeyError, json.JSONDecodeError, OSError, ValueError) as exc:
        print(f"USDA crop supply-demand factory input error: {exc}", file=sys.stderr)
        return 2

    summary = render_usda_crop_factory_markdown(payload)
    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    if args.summary_out is not None:
        args.summary_out.parent.mkdir(parents=True, exist_ok=True)
        args.summary_out.write_text(summary + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False) if args.json else summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
