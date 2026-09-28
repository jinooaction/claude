"""Immutable public filing receipts; source timestamps confer no availability."""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass, fields
from datetime import datetime
from pathlib import Path
from types import MappingProxyType
from uuid import UUID

MAX_BYTES = 8 * 1024 * 1024


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError(reason)


def _matches(value: object, pattern: str) -> bool:
    return isinstance(value, str) and re.fullmatch(pattern, value) is not None


def utc(value: str) -> datetime:
    """Accept only explicit UTC; never guess a naive timestamp's zone."""
    _require(_matches(value, r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z"),
             "invalid UTC timestamp")
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _digest(value: str) -> None:
    _require(_matches(value, r"[0-9a-f]{64}"), "invalid digest")


@dataclass(frozen=True)
class Observation:
    """A validated receipt, not a reviewed earnings event or trading signal."""

    observation_id: str
    issuer_cik: str
    accession: str | None
    source_kind: str
    url: str
    blob_sha256: str
    requested_at: str
    received_at: str
    verified_at: str
    source_claims: Mapping[str, str]

    def __post_init__(self) -> None:
        _require(isinstance(self.observation_id, str), "invalid observation ID")
        try:
            canonical = str(UUID(self.observation_id))
        except (ValueError, AttributeError) as exc:
            raise ValueError("invalid observation ID") from exc
        _require(canonical == self.observation_id, "noncanonical observation ID")
        _require(_matches(self.issuer_cik, r"[0-9]{10}") and int(self.issuer_cik) > 0,
                 "invalid issuer CIK")
        _digest(self.blob_sha256)
        _require(utc(self.requested_at) <= utc(self.received_at) <= utc(self.verified_at),
                 "observation clock reversal")
        _require(isinstance(self.source_claims, Mapping), "invalid source claims")
        _require(set(self.source_claims) <= {
            "acceptance_datetime", "filing_date", "report_date", "form", "primary_document",
        }, "unexpected source claim")
        _require(all(isinstance(value, str) and len(value) <= 256
                     and all(ord(char) >= 32 for char in value)
                     for value in self.source_claims.values()), "invalid source claim")
        object.__setattr__(self, "source_claims", MappingProxyType(dict(self.source_claims)))
        if self.source_kind == "listing":
            _require(self.accession is None, "listing cannot claim an accession")
            _require(self.url == f"https://data.sec.gov/submissions/CIK{self.issuer_cik}.json",
                     "listing URL identity mismatch")
        elif self.source_kind == "primary":
            _require(_matches(self.accession, r"[0-9]{10}-[0-9]{2}-[0-9]{6}"),
                     "invalid accession")
            prefix = (f"https://www.sec.gov/Archives/edgar/data/{int(self.issuer_cik)}/"
                      f"{self.accession.replace('-', '')}/")
            _require(isinstance(self.url, str) and self.url.startswith(prefix),
                     "primary URL identity mismatch")
            name = self.url[len(prefix):]
            _require(_matches(name, r"[A-Za-z0-9][A-Za-z0-9_.-]*\.(?:htm|html|txt)"),
                     "invalid primary document path")
            if "primary_document" in self.source_claims:
                _require(self.source_claims["primary_document"] == name,
                         "primary document claim mismatch")
        else:
            raise ValueError("invalid source kind")

    @property
    def available_at(self) -> str:
        """Receipt lower bound only; queries must also enforce run finalization."""
        return self.verified_at

    def to_dict(self) -> dict:
        result = {field.name: getattr(self, field.name) for field in fields(self)}
        result["source_claims"] = dict(self.source_claims)
        return result

    @classmethod
    def from_dict(cls, value: dict) -> Observation:
        _require(isinstance(value, dict) and set(value) == {f.name for f in fields(cls)},
                 "unexpected or missing observation fields")
        return cls(**value)


def _no_symlink(path: Path) -> None:
    for component in (path, *path.parents):
        _require(not component.is_symlink(), "symlink in evidence path")


class BlobStore:
    """Content-addressed, bounded, exclusive publication of original bytes.

    The caller must serialize store writers. A blob alone is never queryable
    evidence: completed run manifests will supply the visibility boundary.
    """

    def __init__(self, root: Path, *, max_bytes: int = MAX_BYTES) -> None:
        self.root = Path(root).absolute()
        _no_symlink(self.root)
        _require(type(max_bytes) is int and 0 < max_bytes <= MAX_BYTES, "invalid size limit")
        self.max_bytes = max_bytes
        self.directory = self.root / "blobs"
        _no_symlink(self.directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def read(self, digest: str) -> bytes:
        _digest(digest)
        path = self.directory / digest
        _no_symlink(path)
        _require(path.is_file(), "missing blob")
        with path.open("rb") as source:
            raw = source.read(self.max_bytes + 1)
        _require(len(raw) <= self.max_bytes, "blob size limit exceeded")
        _require(hashlib.sha256(raw).hexdigest() == digest, "blob digest mismatch")
        return raw

    def put(self, raw: bytes) -> str:
        _require(isinstance(raw, bytes) and len(raw) <= self.max_bytes,
                 "blob size or type invalid")
        digest = hashlib.sha256(raw).hexdigest()
        path = self.directory / digest
        _no_symlink(path)
        if path.exists():
            self.read(digest)
            return digest
        # Hard-link publishes complete fsynced bytes without replacing an existing file.
        descriptor, temporary = tempfile.mkstemp(prefix=".pending-", dir=self.directory)
        try:
            with os.fdopen(descriptor, "wb") as target:
                target.write(raw)
                target.flush()
                os.fsync(target.fileno())
            try:
                os.link(temporary, path)
            except FileExistsError:
                self.read(digest)
        finally:
            os.unlink(temporary)
        return digest
