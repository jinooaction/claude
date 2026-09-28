"""Immutable public filing receipts; source timestamps confer no availability."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass, fields
from datetime import UTC, datetime
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


def _sync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


class BlobStore:
    """Content-addressed, bounded, exclusive publication of original bytes.

    The caller must serialize store writers. A blob alone is never queryable
    evidence: completed run manifests will supply the visibility boundary.
    """

    def __init__(self, root: Path, *, max_bytes: int = MAX_BYTES,
                 read_only: bool = False) -> None:
        self.root = Path(root).absolute()
        _no_symlink(self.root)
        _require(type(max_bytes) is int and 0 < max_bytes <= MAX_BYTES, "invalid size limit")
        self.max_bytes = max_bytes
        self.read_only = read_only
        self.directory = self.root / "blobs"
        _no_symlink(self.directory)
        if read_only:
            _require(self.directory.is_dir(), "missing blob directory")
        else:
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
        _require(not self.read_only, "read-only blob store")
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
                _sync_directory(path.parent)
            except FileExistsError:
                self.read(digest)
        finally:
            os.unlink(temporary)
        return digest


def _fields(value: object, expected: set[str]) -> dict:
    _require(isinstance(value, dict) and set(value) == expected,
             "unexpected or missing fields")
    return value


def _encode(value: dict) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=True, allow_nan=False) + "\n").encode()


def _hash(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _load(path: Path) -> tuple[dict, bytes]:
    _no_symlink(path)
    _require(path.is_file(), "missing evidence file")
    with path.open("rb") as source:
        raw = source.read(MAX_BYTES + 1)
    _require(len(raw) <= MAX_BYTES, "JSON size limit exceeded")

    def unique(pairs):
        result = {}
        for key, value in pairs:
            _require(key not in result, "duplicate JSON field")
            result[key] = value
        return result

    def invalid_constant(_):
        raise ValueError("invalid JSON constant")

    try:
        value = json.loads(raw, object_pairs_hook=unique, parse_constant=invalid_constant)
    except (UnicodeError, RecursionError) as exc:
        raise ValueError("invalid JSON encoding or nesting") from exc
    _require(isinstance(value, dict), "expected JSON object")
    return value, raw


def _publish_file(path: Path, raw: bytes) -> None:
    _no_symlink(path)
    _require(len(raw) <= MAX_BYTES, "JSON size limit exceeded")
    descriptor, temporary = tempfile.mkstemp(prefix=".pending-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as target:
            target.write(raw)
            target.flush()
            os.fsync(target.fileno())
        try:
            os.link(temporary, path)
            _sync_directory(path.parent)
        except FileExistsError as exc:
            raise ValueError("duplicate evidence file") from exc
    finally:
        os.unlink(temporary)


def _manifest(value: dict) -> None:
    expected = {
        "schema_version", "run_id", "source_commit", "config_sha256", "started_at",
        "ended_at", "previous_run_sha256", "observations", "failures", "coverage", "circuit",
    }
    if isinstance(value, dict) and "recovery_sha256" in value:
        expected.add("recovery_sha256")
        _digest(value["recovery_sha256"])
    _fields(value, expected)
    _require(type(value["schema_version"]) is int and value["schema_version"] == 1,
             "invalid schema version")
    _require(_matches(value["run_id"], r"[A-Za-z0-9][A-Za-z0-9_-]{0,99}"), "invalid run ID")
    _require(_matches(value["source_commit"], r"[a-f0-9]{40}"), "invalid source commit")
    _digest(value["config_sha256"])
    if value["previous_run_sha256"] is not None:
        _digest(value["previous_run_sha256"])
    _require(utc(value["started_at"]) <= utc(value["ended_at"]), "run clock reversal")
    _require(isinstance(value["observations"], list) and isinstance(value["failures"], list),
             "invalid run evidence lists")
    seen = set()
    for reference in value["observations"]:
        _fields(reference, {"observation_id", "sha256"})
        identity = reference["observation_id"]
        _require(_matches(identity, r"[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}"),
                 "invalid observation reference")
        _require(identity not in seen, "duplicate observation reference")
        seen.add(identity)
        _digest(reference["sha256"])
    for failure in value["failures"]:
        expected = {"issuer_cik", "code"}
        if isinstance(failure, dict) and "source_kind" in failure:
            expected |= {"source_kind", "accession"}
        _fields(failure, expected)
        if "source_kind" in failure:
            _require(failure["source_kind"] in {"listing", "primary"}, "invalid failure kind")
            if failure["source_kind"] == "listing":
                _require(failure["accession"] is None, "invalid listing failure accession")
            else:
                _require(_matches(failure["accession"], r"[0-9]{10}-[0-9]{2}-[0-9]{6}"),
                         "invalid primary failure accession")
        _require(_matches(failure["issuer_cik"], r"[0-9]{10}")
                 and int(failure["issuer_cik"]) > 0, "invalid failure issuer")
        _require(failure["code"] in {
            "http_403", "http_429", "http_4xx", "http_5xx", "network", "timeout",
            "invalid_response", "size_limit", "clock_reversal", "cooldown", "run_budget",
        }, "invalid failure code")
    coverage = _fields(value["coverage"], {"succeeded", "failed", "skipped"})
    _require(all(type(count) is int and count >= 0 for count in coverage.values()),
             "invalid coverage count")
    _require(coverage["succeeded"] == len(value["observations"])
             and coverage["failed"] == len(value["failures"]), "coverage mismatch")
    circuit = _fields(value["circuit"], {"consecutive_failures", "cooldown_until"})
    _require(type(circuit["consecutive_failures"]) is int
             and circuit["consecutive_failures"] >= 0, "invalid circuit counter")
    if circuit["cooldown_until"] is not None:
        utc(circuit["cooldown_until"])


class RunStore:
    """Single-writer chain of completed manifests and their immutable receipts.

    A run envelope is the atomic completion marker. Its digest links the next
    run. Hashes detect corruption against that chain, not hostile rewriting of
    an entire history; remote append-only publication supplies that anchor.
    """

    def __init__(self, root: Path, *, clock: Callable[[], str] | None = None,
                 read_only: bool = False, _recovery_depth: int = 0) -> None:
        self.recovery_depth = _recovery_depth
        self.blobs = BlobStore(root, read_only=read_only)
        self.read_only = read_only
        self.root = self.blobs.root
        self.clock = clock or (lambda: datetime.now(UTC).isoformat().replace("+00:00", "Z"))
        for name in ("runs", "observations"):
            path = self.root / name
            _no_symlink(path)
            if read_only:
                _require(path.is_dir(), "missing evidence directory")
            else:
                path.mkdir(exist_ok=True)

    def _receipts(self, manifest: dict) -> list[Observation]:
        result = []
        for reference in manifest["observations"]:
            path = self.root / "observations" / f"{reference['observation_id']}.json"
            value, raw = _load(path)
            _require(_hash(raw) == reference["sha256"], "receipt digest mismatch")
            item = Observation.from_dict(value)
            _require(item.observation_id == reference["observation_id"], "receipt ID mismatch")
            _require(utc(manifest["started_at"]) <= utc(item.requested_at)
                     <= utc(item.verified_at) <= utc(manifest["ended_at"]),
                     "receipt outside run interval")
            self.blobs.read(item.blob_sha256)
            result.append(item)
        return result

    def verify(self) -> list[dict]:
        """Validate the entire completed chain; return it in causal order."""
        directory = self.root / "runs"
        _no_symlink(directory)
        children = {}
        identities = {}

        def register(item):
            identity = item["observation_id"]
            receipt = {field.name: item[field.name] for field in fields(Observation)}
            _require(identity not in identities or identities[identity] == receipt,
                     "conflicting recovered observation ID")
            identities[identity] = receipt
        for path in directory.iterdir():
            _no_symlink(path)
            if path.name.startswith(".pending-"):
                continue
            _require(path.suffix == ".json", "unexpected run file")
            envelope, raw = _load(path)
            _fields(envelope, {"manifest", "manifest_sha256", "finalized_at"})
            manifest = envelope["manifest"]
            _require(_hash(_encode(manifest)) == envelope["manifest_sha256"],
                     "manifest digest mismatch")
            _manifest(manifest)
            _require(path.name == f"{manifest['run_id']}.json", "run filename mismatch")
            _require(utc(manifest["ended_at"]) <= utc(envelope["finalized_at"]),
                     "finalization clock reversal")
            for receipt in self._receipts(manifest):
                register(receipt.to_dict())
            if "recovery_sha256" in manifest:
                from auto_invest.analytics.filing_recovery import recovery_view

                recovered = recovery_view(self, manifest["recovery_sha256"])
                for item in recovered["observations"]:
                    register(item)
                _require(all(utc(item["finalized_at"]) <= utc(manifest["started_at"])
                             for item in recovered["runs"]), "recovery clock reversal")
            parent = manifest["previous_run_sha256"]
            _require(parent not in children, "forked run chain")
            children[parent] = {**envelope, "sha256": _hash(raw)}
        ordered, seen = [], set()
        parent, previous_time = None, None
        while parent in children:
            run = children.pop(parent)
            manifest = run["manifest"]
            if previous_time is not None:
                _require(previous_time <= utc(manifest["started_at"]), "cross-run clock reversal")
            for reference in manifest["observations"]:
                _require(reference["observation_id"] not in seen, "duplicate receipt across runs")
                seen.add(reference["observation_id"])
            ordered.append(run)
            previous_time = utc(run["finalized_at"])
            parent = run["sha256"]
        _require(not children, "broken or cyclic previous run chain")
        return ordered

    def publish(self, manifest: dict, observations: list[Observation]) -> str:
        """Publish a run after all referenced bytes verify; never rewrite an ID."""
        _require(not self.read_only, "read-only run store")
        manifest = json.loads(_encode(manifest))
        _require(isinstance(manifest, dict) and "observations" in manifest,
                 "missing manifest fields")
        _require(manifest["observations"] == [], "caller cannot inject receipt references")
        manifest["observations"] = [{"observation_id": item.observation_id,
                                     "sha256": _hash(_encode(item.to_dict()))}
                                    for item in observations]
        _manifest(manifest)
        runs = self.verify()
        _require(all(run["manifest"]["run_id"] != manifest["run_id"] for run in runs),
                 "duplicate run ID")
        expected_parent = runs[-1]["sha256"] if runs else None
        _require(manifest["previous_run_sha256"] == expected_parent, "previous run mismatch")
        if runs:
            _require(utc(runs[-1]["finalized_at"]) <= utc(manifest["started_at"]),
                     "cross-run clock reversal")
        existing = {}
        if runs and ("recovery_sha256" in manifest or any(
                "recovery_sha256" in run["manifest"] for run in runs)):
            existing = {item["observation_id"]: item
                        for item in self.query(runs[-1]["finalized_at"])["observations"]}
        for item in observations:
            _require(item.observation_id not in existing, "duplicate recovered observation ID")
            _require(utc(manifest["started_at"]) <= utc(item.requested_at)
                     <= utc(item.verified_at) <= utc(manifest["ended_at"]),
                     "receipt outside run interval")
            self.blobs.read(item.blob_sha256)
        for item in observations:
            _publish_file(self.root / "observations" / f"{item.observation_id}.json",
                          _encode(item.to_dict()))
        self._receipts(manifest)
        if "recovery_sha256" in manifest:
            from auto_invest.analytics.filing_recovery import recovery_view

            recovered = recovery_view(self, manifest["recovery_sha256"])
            for item in recovered["observations"]:
                old = existing.get(item["observation_id"])
                _require(old is None or all(old[field.name] == item[field.name]
                                           for field in fields(Observation)),
                         "conflicting recovered observation ID")
            _require(all(utc(item["finalized_at"]) <= utc(manifest["started_at"])
                         for item in recovered["runs"]), "recovery clock reversal")
        finalized = self.clock()
        _require(utc(manifest["ended_at"]) <= utc(finalized), "finalization clock reversal")
        raw = _encode({"manifest": manifest, "manifest_sha256": _hash(_encode(manifest)),
                       "finalized_at": finalized})
        _publish_file(self.root / "runs" / f"{manifest['run_id']}.json", raw)
        return _hash(raw)

    def query(self, as_of: str) -> dict:
        cutoff = utc(as_of)
        runs, observations, recovered_runs = [], [], []
        seen = {}

        def add(item):
            identity = item["observation_id"]
            receipt = {field.name: item[field.name] for field in fields(Observation)}
            if identity in seen:
                _require(seen[identity] == receipt, "conflicting recovered observation ID")
                return
            seen[identity] = receipt
            observations.append(item)
        for run in self.verify():
            if utc(run["finalized_at"]) > cutoff:
                continue
            manifest = run["manifest"]
            runs.append(run)
            for item in self._receipts(manifest):
                if utc(item.verified_at) <= cutoff:
                    add({**item.to_dict(), "run_id": manifest["run_id"],
                         "available_at": run["finalized_at"]})
            if "recovery_sha256" in manifest:
                from auto_invest.analytics.filing_recovery import recovery_view

                recovered = recovery_view(self, manifest["recovery_sha256"])
                recovered_runs.extend(recovered["runs"] + recovered["recovered_runs"])
                for item in recovered["observations"]:
                    add({**item, "recovered_from_run_id": item["run_id"],
                         "run_id": manifest["run_id"], "available_at": run["finalized_at"]})
        return {"as_of": as_of, "scope": "collector_local_observation_only",
                "observations": observations, "runs": runs, "recovered_runs": recovered_runs}
