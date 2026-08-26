#!/usr/bin/env python3
"""Evaluate the latest first-entry contract before a signed live order request."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import tomllib
from decimal import Decimal
from pathlib import Path

from auto_invest.config.rules import PortfolioRebalanceConfig
from auto_invest.portfolio.autoarm import strategy_fingerprint_digest

_ROOT = Path(__file__).resolve().parents[1]
_CORE_PATH = _ROOT / "src" / "auto_invest" / "portfolio" / "live_entry_revalidation.py"
_SPEC = importlib.util.spec_from_file_location("live_entry_revalidation_core", _CORE_PATH)
if _SPEC is None or _SPEC.loader is None:
    raise RuntimeError(f"cannot load live entry revalidation core: {_CORE_PATH}")
_CORE = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _CORE
_SPEC.loader.exec_module(_CORE)
evaluate_live_entry = _CORE.evaluate_live_entry


def _read(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profit-evidence-json", type=Path, required=True)
    parser.add_argument("--factory-evidence-json", type=Path)
    parser.add_argument("--hardened-canary-json", type=Path, required=True)
    parser.add_argument("--live-performance-json", type=Path, required=True)
    parser.add_argument("--evidence-age-hours", type=float, required=True)
    parser.add_argument("--factory-evidence-age-hours", type=float)
    parser.add_argument("--live-portfolio", type=Path)
    parser.add_argument("--fundability-preview-json", type=Path, required=True)
    parser.add_argument("--capital-usd", type=Decimal, required=True)
    parser.add_argument("--max-evidence-age-hours", type=float, default=36.0)
    args = parser.parse_args(argv)

    live_fingerprint = None
    if args.live_portfolio is not None:
        try:
            raw = tomllib.loads(args.live_portfolio.read_text(encoding="utf-8"))
            config = PortfolioRebalanceConfig.model_validate(raw["portfolio"])
            live_fingerprint = strategy_fingerprint_digest(config)
        except (OSError, KeyError, ValueError, tomllib.TOMLDecodeError):
            live_fingerprint = None

    fundability_preview = _read(args.fundability_preview_json)
    fundability_evidence = (
        fundability_preview.get("fundability")
        if isinstance(fundability_preview, dict)
        else None
    )
    result = evaluate_live_entry(
        _read(args.profit_evidence_json),
        _read(args.hardened_canary_json),
        _read(args.live_performance_json),
        evidence_age_hours=args.evidence_age_hours,
        max_evidence_age_hours=args.max_evidence_age_hours,
        factory_evidence=(
            _read(args.factory_evidence_json) if args.factory_evidence_json is not None else None
        ),
        factory_evidence_age_hours=args.factory_evidence_age_hours,
        live_strategy_fingerprint=live_fingerprint,
        fundability_evidence=fundability_evidence,
        expected_capital_usd=args.capital_usd,
    )
    print(json.dumps(result.as_dict(), ensure_ascii=False, sort_keys=True))
    return 0 if result.allowed else 3


if __name__ == "__main__":
    raise SystemExit(main())
