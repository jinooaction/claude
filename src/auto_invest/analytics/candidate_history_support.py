"""Candidate result history support manifest.

This module is intentionally small and deterministic. It is the single map from
candidate portfolio TOMLs to the read-only server DBs that can be exported into
ingested history datasets before candidate validation runs.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any

SCHEMA_VERSION = "1.0"
CANDIDATE_RESULT_HISTORY_ROOT = "/tmp/candidate_result_history"


@dataclass(frozen=True)
class CandidateHistoryDataset:
    key: str
    portfolio_path: str
    db_path: str
    history_root: str

    def as_dict(self) -> dict[str, str]:
        return {
            "key": self.key,
            "portfolio_path": self.portfolio_path,
            "db_path": self.db_path,
            "history_root": self.history_root,
        }

    def manifest_row(self) -> str:
        return "\t".join(
            (self.key, self.portfolio_path, self.db_path, self.history_root)
        )


def _history_root(key: str) -> str:
    return f"{CANDIDATE_RESULT_HISTORY_ROOT}/{key}/hist"


CANDIDATE_HISTORY_DATASETS: tuple[CandidateHistoryDataset, ...] = (
    CandidateHistoryDataset(
        key="micro-gtaa",
        portfolio_path="deploy/micro-gtaa-live-portfolio.toml",
        db_path="data/auto_invest.db",
        history_root=_history_root("micro-gtaa"),
    ),
    CandidateHistoryDataset(
        key="global-trend-fixed",
        portfolio_path="deploy/global-trend-fixed-portfolio.toml",
        db_path="data/forward_v2_globalfixed.db",
        history_root=_history_root("global-trend-fixed"),
    ),
    CandidateHistoryDataset(
        key="global-trend-wide",
        portfolio_path="deploy/global-trend-wide-portfolio.toml",
        db_path="data/forward_v2_wide.db",
        history_root=_history_root("global-trend-wide"),
    ),
    CandidateHistoryDataset(
        key="multi-asset-trend",
        portfolio_path="deploy/multi-asset-trend-portfolio.toml",
        db_path="data/forward_v2_multiasset.db",
        history_root=_history_root("multi-asset-trend"),
    ),
)


def _normalize_portfolio_path(value: object) -> str:
    return str(PurePosixPath(str(value)))


_DATASET_BY_PORTFOLIO: dict[str, CandidateHistoryDataset] = {
    _normalize_portfolio_path(dataset.portfolio_path): dataset
    for dataset in CANDIDATE_HISTORY_DATASETS
}


def candidate_history_datasets() -> tuple[CandidateHistoryDataset, ...]:
    return CANDIDATE_HISTORY_DATASETS


def history_dataset_for_portfolio(
    portfolio_path: object,
) -> CandidateHistoryDataset | None:
    return _DATASET_BY_PORTFOLIO.get(_normalize_portfolio_path(portfolio_path))


def require_history_root_for_portfolio(portfolio_path: object) -> str:
    dataset = history_dataset_for_portfolio(portfolio_path)
    if dataset is None:
        raise KeyError(f"candidate history dataset is not defined for {portfolio_path!r}")
    return dataset.history_root


def manifest_lines() -> tuple[str, ...]:
    return tuple(dataset.manifest_row() for dataset in CANDIDATE_HISTORY_DATASETS)


def manifest_document() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "history_root": CANDIDATE_RESULT_HISTORY_ROOT,
        "datasets": [dataset.as_dict() for dataset in CANDIDATE_HISTORY_DATASETS],
    }


__all__ = [
    "CANDIDATE_HISTORY_DATASETS",
    "CANDIDATE_RESULT_HISTORY_ROOT",
    "CandidateHistoryDataset",
    "SCHEMA_VERSION",
    "candidate_history_datasets",
    "history_dataset_for_portfolio",
    "manifest_document",
    "manifest_lines",
    "require_history_root_for_portfolio",
]
