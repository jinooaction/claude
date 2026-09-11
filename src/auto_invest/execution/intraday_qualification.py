"""Recompute strategy evidence and consume a separate server-owned authorization.

The authorization is an operator attestation, not machine proof of execution
parity/canary/deployment. This module never issues that attestation or activates
an account. Research and forward evidence are independently recomputed here.
"""

import hashlib
import json
import os
import re
import stat
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

from auto_invest.analytics.intraday_paper_challenger import load_preregistration
from auto_invest.execution.intraday_execution_evidence import (
    ExecutionCostAssessment,
    ExecutionCostSource,
)
from auto_invest.execution.intraday_observation_models import ObservationModelError
from auto_invest.execution.intraday_registration import assess_registered_forward
from auto_invest.execution.intraday_selection import ResearchSelection, select_research
from auto_invest.execution.intraday_signals import execution_fingerprint
from auto_invest.execution.preparation import confirmed_budget
from auto_invest.market_data.intraday import DataError, digest, utc

AUTHORIZATION_PATH = Path("/etc/auto-invest/intraday-execution-authorization.json")
ROOT = Path(__file__).resolve().parents[3]
PREREGISTRATION = (
    ROOT / "specs/177-intraday-paper-challenger/contracts/intraday-preregistration.json"
)


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError
        result[key] = value
    return result


def _read_authorization():
    """Fixed protected server file, no environment/path/CLI override."""
    try:
        fd = os.open(AUTHORIZATION_PATH, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            info = os.fstat(fd)
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0
                    or stat.S_IMODE(info.st_mode) & 0o137 or not 0 < info.st_size <= 16384):
                raise ValueError
            raw = os.read(fd, 16385)
            after = os.fstat(fd)
            if len(raw) != info.st_size or any(getattr(info, k) != getattr(after, k) for k in (
                    "st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")):
                raise ValueError
        finally:
            os.close(fd)
        result = json.loads(raw, object_pairs_hook=_unique)
        if not isinstance(result, dict):
            raise ValueError
        return result
    except (OSError, ValueError, TypeError, UnicodeError):
        raise DataError("INTRADAY_AUTHORIZATION_UNAVAILABLE") from None


@dataclass(frozen=True)
class ExecutionQualification:
    selection: ResearchSelection
    account_digest: str
    capital_limit: Decimal
    registration_digest: str
    complete_sessions: int
    runtime_digest: str
    execution_cost: ExecutionCostAssessment
    interval_model_json: str = "{}"

    def __call__(self):
        """Synchronous last-boundary check; no broker calls or authority issuance."""
        try:
            selected = self.selection
            if (selected.candidate is None or selected.execution_identity != execution_fingerprint(
                    selected.candidate, selected.provider)):
                return "QUALIFICATION_STRATEGY_CHANGED"
            if (self.execution_cost.account_digest != self.account_digest
                    or self.execution_cost.execution_identity != selected.execution_identity
                    or self.execution_cost.runtime_digest != self.runtime_digest
                    or self.execution_cost.issues):
                return "QUALIFICATION_EXECUTION_BINDING_MISMATCH"
            grant = _read_authorization()
            identity = dict(
                account_digest=self.account_digest,
                execution_identity=selected.execution_identity,
                research_digest=selected.research_digest,
                dataset_fingerprint=selected.dataset_fingerprint,
                registration_digest=self.registration_digest,
                runtime_digest=self.runtime_digest,
                capital_limit_usd=format(self.capital_limit.normalize(), "f"),
                broker_execution_parity_digest=self.execution_cost.digest,
            )
            evidence_fields = {
                "hardened_canary_digest",
                "deployment_audit_digest",
            }
            if (set(grant) != set(identity) | evidence_fields | {
                    "schema", "scope", "authorization_id", "valid_from", "valid_until"}
                    or type(grant["schema"]) is not int or grant["schema"] != 1
                    or grant["scope"] != "intraday-repeated-orders"
                    or any(grant[k] != value for k, value in identity.items())
                    or not isinstance(grant["authorization_id"], str)
                    or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", grant["authorization_id"])
                    or any(not isinstance(grant[k], str) or not re.fullmatch(
                        r"sha256:[0-9a-f]{64}", grant[k]) for k in evidence_fields)):
                return "QUALIFICATION_AUTHORIZATION_MISMATCH"
            now = datetime.now(UTC)
            if not utc(grant["valid_from"]) <= now < utc(grant["valid_until"]):
                return "QUALIFICATION_AUTHORIZATION_EXPIRED"
            if self.execution_cost.missing_model_conditions:
                return "QUALIFICATION_EXECUTION_MODEL_EVIDENCE_MISSING"
            return None
        except Exception:
            return "QUALIFICATION_AUTHORIZATION_UNAVAILABLE"


async def prepare_qualification(*, archives: Path, forward_database: Path,
                          registration: Path, account: str, capital_limit: Decimal,
                          runtime_digest: str, execution_source=None):
    """Run expensive evidence checks once, then return a revocable server guard.

    Receipt of a returned object does not imply authorization: call it before
    launch and at every broker write. A removed/changed/expired grant is refused.
    The registration and preregistration used for all checks are copied once.
    """
    if not isinstance(account, str) or not re.fullmatch(r"[0-9]{10}", account):
        raise DataError("QUALIFICATION_ACCOUNT_INVALID")
    if (not isinstance(runtime_digest, str)
            or not re.fullmatch(r"sha256:[0-9a-f]{64}", runtime_digest)):
        raise DataError("QUALIFICATION_RUNTIME_INVALID")
    budget = confirmed_budget(
        ROOT / "specs/182-intraday-kis-execution/contracts/confirmed-budget.json",
    )
    if (not isinstance(capital_limit, Decimal) or not capital_limit.is_finite()
            or not 0 < capital_limit <= Decimal(budget["capital_limit_usd"])):
        raise DataError("QUALIFICATION_CAPITAL_INVALID")
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
        with TemporaryDirectory(prefix="intraday-qualify-") as directory:
            prereg = Path(directory) / "preregistration.json"
            prereg.write_bytes(PREREGISTRATION.read_bytes())
            with registration.open("rb") as source:
                record = source.read(16385)
            selected = select_research(archives, prereg, commit)
            if (selected.candidate is None or selected.execution_identity is None
                    or selected.verdict != "PAPER_CHALLENGER"
                    or selected.provider != "kis-nasdaq-partial-unadjusted"):
                raise DataError("QUALIFICATION_RESEARCH_NOT_ACCEPTED")
            forward = assess_registered_forward(forward_database, record, selected, prereg,
                                                include_interval_bars=True)
            if (forward.get("freeze_authentication_verified") is not True
                    or forward.get("minimum_observation_count_met") is not True
                    or type(forward.get("complete_sessions")) is not int
                    or type(forward.get("required_sessions")) is not int
                    or forward["required_sessions"] != 60
                    or forward["complete_sessions"] < 60
                    or type(forward.get("invalid_sessions")) is not int
                    or forward.get("invalid_sessions") != 0):
                raise DataError("QUALIFICATION_FORWARD_NOT_ACCEPTED")
            if not isinstance(execution_source, ExecutionCostSource):
                raise DataError("QUALIFICATION_EXECUTION_SOURCE_REQUIRED")
            cost = await execution_source.assess(
                selected, forward.get("session_dates", []),
                load_preregistration(prereg)["cost_models"]["base"]["commission_bps_per_side"],
            )
            account_digest = "sha256:" + hashlib.sha256(account.encode()).hexdigest()
            dates = sorted(day.replace("-", "") for day in forward.get("session_dates", []))
            if (not isinstance(cost, ExecutionCostAssessment) or not dates
                    or cost.account_digest != account_digest
                    or cost.execution_identity != selected.execution_identity
                    or cost.runtime_digest != runtime_digest
                    or cost.window != (dates[0], dates[-1])):
                raise DataError("QUALIFICATION_EXECUTION_BINDING_MISMATCH")
            if cost.issues:
                raise DataError("QUALIFICATION_EXECUTION_COSTS_NOT_ACCEPTED")
            bars_json = forward.get("_interval_bars_json")
            if bars_json is None:
                interval_model = dict(interval_volume_verified=False,
                                      issues=["FORWARD_INTERVAL_BARS_UNAVAILABLE"])
            elif cost.intervals_json == "[]":
                interval_model = dict(interval_volume_verified=False,
                                      issues=["EXECUTION_INTERVAL_BOUNDS_UNAVAILABLE"])
            else:
                try:
                    interval_model = cost.assess_interval_volume(
                        json.loads(bars_json),
                        participation=str(load_preregistration(prereg)["cost_models"]["base"][
                            "max_volume_participation"]),
                        observed_at=datetime.now(UTC).isoformat(),
                    )
                    # Same independently replayed snapshot and signed freeze;
                    # this does not cryptographically authenticate market data.
                    interval_model["registered_forward_replay_verified"] = True
                except ObservationModelError as error:
                    interval_model = dict(interval_volume_verified=False, issues=[str(error)])
        return ExecutionQualification(
            selected, "sha256:" + hashlib.sha256(account.encode()).hexdigest(),
            capital_limit, digest(record), forward["complete_sessions"], runtime_digest, cost,
            json.dumps(interval_model, sort_keys=True, separators=(",", ":"), allow_nan=False),
        )
    except DataError:
        raise
    except Exception:
        raise DataError("QUALIFICATION_EVIDENCE_UNAVAILABLE") from None
