"""Select a research candidate by recomputation, never by accepting a PASS file."""

import json
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from auto_invest.analytics.intraday_archive import review_archives
from auto_invest.analytics.intraday_paper_challenger import (
    IntradayCandidate,
    build_candidate_registry,
    load_preregistration,
)
from auto_invest.execution.intraday_signals import execution_fingerprint
from auto_invest.market_data.intraday import digest


@dataclass(frozen=True)
class ResearchSelection:
    candidate: IntradayCandidate | None
    provider: str
    code_commit: str
    dataset_fingerprint: str
    research_digest: str
    execution_identity: str | None
    verdict: str
    session_count: int
    missing_sessions: int

    def public(self):
        return dict(
            status="RESEARCH_CANDIDATE_SELECTED" if self.candidate else "RESEARCH_NOT_ACCEPTED",
            candidate_id=self.candidate.candidate_id if self.candidate else None,
            verdict=self.verdict, session_count=self.session_count,
            missing_sessions=self.missing_sessions, provider=self.provider,
            code_commit=self.code_commit, dataset_fingerprint=self.dataset_fingerprint,
            research_digest=self.research_digest, execution_identity=self.execution_identity,
            live_eligible=False, orders_submitted=0,
        )


def select_research(archives: Path, preregistration: Path, code_commit: str) -> ResearchSelection:
    """No account, authority, provider parity or forward qualification is issued."""
    with TemporaryDirectory(prefix="intraday-selection-") as temporary:
        # Freeze preregistration once: analysis and candidate construction read
        # exactly the same bytes even if the source path is edited concurrently.
        frozen = Path(temporary) / "preregistration.json"
        frozen.write_bytes(preregistration.read_bytes())
        output = Path(temporary) / "research"
        result = review_archives(archives, output, frozen, code_commit)
        raw = (output / "research.json").read_bytes()
        report = json.loads(raw)
        selected = None
        if result["decision"]["passed"] is True:
            if result["decision"]["verdict"] != "PAPER_CHALLENGER" or result["synthetic"]:
                raise ValueError("RESEARCH_RESULT_INVALID")
            registry = build_candidate_registry(load_preregistration(frozen))
            selected_id = report["selection"]["selected_candidate_id"]
            selected = next((c for c in registry if c.candidate_id == selected_id), None)
            if selected is None:
                raise ValueError("RESEARCH_CANDIDATE_INVALID")
        # Provider conversion would need its own validated parity contract.
        identity = (execution_fingerprint(selected, result["provider"])
                    if selected and result["provider"] == "kis-nasdaq-partial-unadjusted"
                    else None)
        return ResearchSelection(
            selected, result["provider"], code_commit, result["dataset_fingerprint"], digest(raw),
            identity, result["decision"]["verdict"], result["session_count"],
            result["missing_sessions"],
        )
