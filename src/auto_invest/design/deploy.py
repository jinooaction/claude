"""Proposal persistence for the rule design command.

Spec 111 removed design-driven live activation. This module keeps the inert
candidate file writer and leaves old live-start helper names as explicit
boundary errors so stale callers fail closed.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import NoReturn


class LiveActivationBoundaryError(RuntimeError):
    """Raised when legacy design-live activation is attempted."""


def prompt_operator_ok(*args: object, **kwargs: object) -> NoReturn:
    """Legacy compatibility guard: design no longer asks for live-start OK."""
    raise LiveActivationBoundaryError(
        "auto-invest design is PROPOSAL_ONLY; live activation must use the "
        "validated promotion/canary path."
    )


def write_auto_rules_file(toml_text: str, *, config_dir: Path) -> Path:
    """Persist generated TOML as an inert candidate rules file."""
    config_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    path = config_dir / f"rules_auto_{ts}.toml"
    path.write_text(toml_text, encoding="utf-8")
    return path


def write_proposal_report(payload: dict[str, object], *, rules_path: Path) -> Path:
    """Persist proposal authority and verification status next to the rules file."""
    report_path = rules_path.with_suffix(".proposal.json")
    report_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report_path


def start_live_worker(*args: object, **kwargs: object) -> NoReturn:
    """Legacy compatibility guard: design cannot start a live process."""
    raise LiveActivationBoundaryError(
        "design-driven live worker startup has been removed; submit the "
        "candidate to the existing validation and canary path instead."
    )
