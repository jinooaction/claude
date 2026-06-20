#!/usr/bin/env python3
"""Local multi-session guard for Codex/Claude work on this repository.

The guard has two jobs:

* SessionStart records a short-lived lease keyed by CODEX_THREAD_ID and reports
  whether another recent session is touching the same worktree or branch.
* Git hooks block the riskiest local operations: direct main commits/pushes and
  commits/pushes while another recent session owns the same worktree or branch.

Set CODEX_CONCURRENCY_GUARD_ALLOW=1 only for an intentional emergency override.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

LEASE_TTL_SECONDS = 4 * 60 * 60
STATE_DIR = Path(".codex/state/concurrency")
SNAPSHOT_DIR = STATE_DIR / "snapshots"
MAX_UNTRACKED_FILES = 80
MAX_UNTRACKED_FILE_BYTES = 512 * 1024
THREAD_ENV_KEYS = (
    "CODEX_THREAD_ID",
    "CLAUDECODE_SESSION_ID",
    "CLAUDE_SESSION_ID",
    "TERM_SESSION_ID",
)
OVERRIDE_ENV = "CODEX_CONCURRENCY_GUARD_ALLOW"


@dataclass(frozen=True)
class CurrentState:
    repo: Path
    worktree: Path
    branch: str
    head: str
    thread_id: str
    dirty_paths: frozenset[str]


@dataclass(frozen=True)
class Lease:
    path: Path
    thread_id: str
    host: str
    worktree: str
    branch: str
    head: str
    updated_at: float
    dirty_paths: frozenset[str]


@dataclass(frozen=True)
class Finding:
    level: str
    message: str


def _run_git(repo: Path | None, *args: str) -> str:
    cmd = ["git", *args]
    out = subprocess.run(
        cmd,
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=5,
    )
    if out.returncode != 0:
        return ""
    return out.stdout.strip()


def _run_git_checked(repo: Path, *args: str) -> str:
    out = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if out.returncode != 0:
        raise RuntimeError(out.stderr.strip() or f"git {' '.join(args)} failed")
    return out.stdout.strip()


def repo_root() -> Path:
    root = _run_git(None, "rev-parse", "--show-toplevel")
    if not root:
        raise RuntimeError("not inside a git worktree")
    return Path(root).resolve()


def _thread_id() -> str:
    for key in THREAD_ENV_KEYS:
        value = os.environ.get(key)
        if value:
            return f"{key}:{value}"
    return f"pid:{os.getppid()}"


def _dirty_paths(porcelain: str) -> frozenset[str]:
    paths: set[str] = set()
    for line in porcelain.splitlines():
        if not line:
            continue
        raw = line[3:] if len(line) > 3 else line
        if " -> " in raw:
            left, right = raw.split(" -> ", 1)
            paths.add(left.strip())
            paths.add(right.strip())
        else:
            paths.add(raw.strip())
    return frozenset(p for p in paths if p)


def _safe_id(value: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in "._-" else "-" for ch in value)
    safe = safe.strip(".-")
    return safe[:80] or "unknown"


def current_state(repo: Path) -> CurrentState:
    worktree = Path(_run_git(repo, "rev-parse", "--show-toplevel") or repo).resolve()
    branch = _run_git(repo, "rev-parse", "--abbrev-ref", "HEAD") or "(unknown)"
    head = _run_git(repo, "rev-parse", "--short", "HEAD") or "(unknown)"
    dirty = _dirty_paths(_run_git(repo, "status", "--porcelain=v1", "-uall"))
    return CurrentState(
        repo=repo,
        worktree=worktree,
        branch=branch,
        head=head,
        thread_id=_thread_id(),
        dirty_paths=dirty,
    )


def _lease_dir(repo: Path) -> Path:
    return repo / STATE_DIR


def _lease_path(repo: Path, state: CurrentState) -> Path:
    key = f"{socket.gethostname()}|{state.thread_id}|{state.worktree}"
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]
    return _lease_dir(repo) / f"{digest}.json"


def write_lease(state: CurrentState) -> None:
    directory = _lease_dir(state.repo)
    directory.mkdir(parents=True, exist_ok=True)
    path = _lease_path(state.repo, state)
    now = time.time()
    payload = {
        "thread_id": state.thread_id,
        "host": socket.gethostname(),
        "worktree": str(state.worktree),
        "branch": state.branch,
        "head": state.head,
        "updated_at": now,
        "dirty_paths": sorted(state.dirty_paths),
    }
    tmp = path.with_name(f"{path.stem}.{os.getpid()}.{time.monotonic_ns()}.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def _untracked_files(repo: Path) -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard", "-z"],
        cwd=repo,
        capture_output=True,
        timeout=5,
    )
    if out.returncode != 0 or not out.stdout:
        return []
    return [p.decode("utf-8", errors="replace") for p in out.stdout.split(b"\0") if p]


def _snapshot_digest(repo: Path, untracked: list[str]) -> tuple[str, str, str]:
    worktree_diff = _run_git(repo, "diff", "--binary")
    index_diff = _run_git(repo, "diff", "--cached", "--binary")
    untracked_meta: list[str] = []
    for rel in untracked[:MAX_UNTRACKED_FILES]:
        path = repo / rel
        try:
            stat = path.stat()
        except OSError:
            continue
        untracked_meta.append(f"{rel}\0{stat.st_size}\0{int(stat.st_mtime_ns)}")
    digest = hashlib.sha256(
        "\n".join([worktree_diff, index_diff, *untracked_meta]).encode("utf-8", errors="replace")
    ).hexdigest()
    return digest, worktree_diff, index_diff


def write_snapshot(state: CurrentState, findings: list[Finding]) -> Path | None:
    """Persist a local recovery snapshot for dirty or risky multi-session state."""
    if not state.dirty_paths and not any(f.level in {"WARN", "BLOCK"} for f in findings):
        return None

    untracked = _untracked_files(state.repo)
    digest, worktree_diff, index_diff = _snapshot_digest(state.repo, untracked)
    root = state.repo / SNAPSHOT_DIR / _safe_id(state.thread_id)
    root.mkdir(parents=True, exist_ok=True)
    last_path = root / "last_snapshot.json"
    if last_path.exists():
        try:
            last = json.loads(last_path.read_text(encoding="utf-8"))
            if last.get("digest") == digest:
                return None
        except (OSError, json.JSONDecodeError):
            pass

    stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    snapshot = root / f"{stamp}-{digest[:12]}"
    snapshot.mkdir(parents=True, exist_ok=True)
    (snapshot / "worktree.diff").write_text(worktree_diff, encoding="utf-8")
    (snapshot / "index.diff").write_text(index_diff, encoding="utf-8")

    copied: list[dict[str, object]] = []
    skipped: list[dict[str, object]] = []
    files_root = snapshot / "untracked"
    for rel in untracked[:MAX_UNTRACKED_FILES]:
        src = state.repo / rel
        try:
            stat = src.stat()
        except OSError:
            continue
        if not src.is_file() or stat.st_size > MAX_UNTRACKED_FILE_BYTES:
            skipped.append({"path": rel, "size": stat.st_size, "reason": "too-large-or-not-file"})
            continue
        dst = files_root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        copied.append({"path": rel, "size": stat.st_size})
    if len(untracked) > MAX_UNTRACKED_FILES:
        skipped.append(
            {
                "path": "...",
                "count": len(untracked) - MAX_UNTRACKED_FILES,
                "reason": "untracked-file-limit",
            }
        )

    metadata = {
        "created_at": time.time(),
        "digest": digest,
        "thread_id": state.thread_id,
        "worktree": str(state.worktree),
        "branch": state.branch,
        "head": state.head,
        "dirty_paths": sorted(state.dirty_paths),
        "findings": [{"level": f.level, "message": f.message} for f in findings],
        "untracked_copied": copied,
        "untracked_skipped": skipped,
    }
    (snapshot / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    last_path.write_text(
        json.dumps(
            {"digest": digest, "path": str(snapshot)},
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return snapshot


def read_leases(repo: Path, *, now: float | None = None) -> list[Lease]:
    now = time.time() if now is None else now
    directory = _lease_dir(repo)
    if not directory.exists():
        return []

    leases: list[Lease] = []
    for path in directory.glob("*.json"):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            updated_at = float(raw.get("updated_at", 0))
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            continue
        if updated_at <= 0 or now - updated_at > LEASE_TTL_SECONDS:
            with contextlib.suppress(OSError):
                path.unlink()
            continue
        leases.append(
            Lease(
                path=path,
                thread_id=str(raw.get("thread_id", "")),
                host=str(raw.get("host", "")),
                worktree=str(raw.get("worktree", "")),
                branch=str(raw.get("branch", "")),
                head=str(raw.get("head", "")),
                updated_at=updated_at,
                dirty_paths=frozenset(str(p) for p in raw.get("dirty_paths", [])),
            )
        )
    return leases


def _dedupe_leases(leases: list[Lease]) -> list[Lease]:
    """Keep the newest lease for the same logical session/worktree/branch."""
    latest: dict[tuple[str, str, str], Lease] = {}
    for lease in leases:
        key = (lease.thread_id, lease.worktree, lease.branch)
        current = latest.get(key)
        if current is None or lease.updated_at > current.updated_at:
            latest[key] = lease
    return sorted(latest.values(), key=lambda lease: lease.updated_at, reverse=True)


def push_targets_main(stdin_text: str) -> bool:
    for line in stdin_text.splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[2] == "refs/heads/main":
            return True
    return False


def evaluate(
    state: CurrentState,
    leases: list[Lease],
    *,
    mode: str,
    push_stdin: str = "",
) -> list[Finding]:
    findings: list[Finding] = []
    others = [
        lease
        for lease in _dedupe_leases(leases)
        if lease.thread_id != state.thread_id
    ]

    if mode in {"pre-commit", "pre-push"} and state.branch == "main":
        findings.append(Finding("BLOCK", "`main` 브랜치에서 직접 커밋하거나 푸시하려고 함."))
    if mode == "pre-push" and push_targets_main(push_stdin):
        findings.append(Finding("BLOCK", "`refs/heads/main`으로 직접 푸시하려고 함."))
    for lease in others:
        reasons: list[str] = []
        if Path(lease.worktree) == state.worktree:
            reasons.append("같은 worktree")
        if lease.branch == state.branch and state.branch not in ("", "(unknown)"):
            reasons.append("같은 브랜치")
        overlap = state.dirty_paths.intersection(lease.dirty_paths)
        if overlap:
            paths = ", ".join(sorted(overlap)[:6])
            reasons.append(f"수정 파일 겹침: {paths}")
        if reasons:
            findings.append(
                Finding(
                    "BLOCK" if mode in {"pre-commit", "pre-push"} else "WARN",
                    "다른 최근 세션과 충돌 가능: "
                    f"{lease.thread_id} ({lease.branch}@{lease.head}, {lease.worktree}) - "
                    + "; ".join(reasons),
                )
            )
    if state.branch == "main" and state.dirty_paths:
        findings.append(Finding("WARN", "`main` 브랜치 작업 트리에 변경 파일이 있음."))
    if not others and not findings:
        findings.append(Finding("OK", "동시 세션 충돌 징후 없음."))
    return findings


def _format_age(seconds: float) -> str:
    minutes = int(seconds // 60)
    if minutes < 60:
        return f"{minutes}분 전"
    return f"{minutes // 60}시간 {minutes % 60}분 전"


def render_report(state: CurrentState, leases: list[Lease], findings: list[Finding]) -> str:
    now = time.time()
    active = [
        lease
        for lease in _dedupe_leases(leases)
        if lease.thread_id != state.thread_id
    ]
    lines = [
        "# local multi-session guard",
        f"current thread : {state.thread_id}",
        f"worktree       : {state.worktree}",
        f"branch/head    : {state.branch}@{state.head}",
        f"dirty paths    : {len(state.dirty_paths)}",
        f"other sessions : {len(active)} recent lease(s)",
    ]
    if active:
        lines.append("recent sessions:")
        for lease in active[:8]:
            lines.append(
                f"  - {lease.thread_id} | {lease.branch}@{lease.head} | "
                f"{lease.worktree} | {_format_age(now - lease.updated_at)}"
            )
    lines.append("findings:")
    lines.extend(f"  - {finding.level}: {finding.message}" for finding in findings)
    if any(f.level == "BLOCK" for f in findings) or any(f.level == "WARN" for f in findings):
        lines += [
            "required action:",
            "  - 쓰기 작업은 세션별 브랜치 또는 `git worktree`로 분리하세요.",
            "  - 즉시 격리하려면 "
            "`python3 scripts/local_concurrency_guard.py --mode isolate`를 실행하세요.",
            "  - 같은 파일을 만지는 세션 하나만 남기고 나머지는 중단하거나 읽기 전용으로 돌리세요.",
        ]
    return "\n".join(lines)


def create_isolated_worktree(state: CurrentState) -> str:
    repo_parent = state.repo.parent / "claude-worktrees"
    repo_parent.mkdir(parents=True, exist_ok=True)
    short_thread = _safe_id(state.thread_id.split(":", 1)[-1])[:16]
    timestamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    branch = f"Codex/isolated-{timestamp}-{short_thread}"
    path = repo_parent / branch.replace("/", "-")
    _run_git_checked(state.repo, "worktree", "add", "-b", branch, str(path), "HEAD")
    _run_git_checked(state.repo, "config", "core.hooksPath", str(state.repo / ".githooks"))
    return "\n".join(
        [
            f"created isolated worktree: {path}",
            f"branch: {branch}",
            f"next command: codex -C {path}",
        ]
    )


def watchdog(interval: float) -> int:
    repo = repo_root()
    while True:
        state = current_state(repo)
        leases = read_leases(repo)
        findings = evaluate(state, leases, mode="check")
        snapshot = write_snapshot(state, findings)
        if snapshot:
            print(f"snapshot: {snapshot}", flush=True)
        time.sleep(interval)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Guard local concurrent Codex/Claude sessions.")
    parser.add_argument(
        "--mode",
        choices=("session-start", "pre-commit", "pre-push", "check", "isolate", "watchdog"),
        default="check",
    )
    parser.add_argument("--interval", type=float, default=10.0)
    args = parser.parse_args(argv)

    try:
        repo = repo_root()
        state = current_state(repo)
        if args.mode == "watchdog":
            return watchdog(max(args.interval, 1.0))
        if args.mode == "isolate":
            print(create_isolated_worktree(state))
            return 0
        if args.mode in {"session-start", "check"}:
            write_lease(state)
        push_stdin = sys.stdin.read() if args.mode == "pre-push" else ""
        leases = read_leases(repo)
        findings = evaluate(state, leases, mode=args.mode, push_stdin=push_stdin)
        snapshot = write_snapshot(state, findings)
        report = render_report(state, leases, findings)
        if snapshot:
            report += f"\nrecovery snapshot: {snapshot}"
    except Exception as exc:
        if args.mode == "session-start":
            json.dump(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "SessionStart",
                        "additionalContext": f"local multi-session guard: non-fatal error: {exc}",
                    },
                    "systemMessage": "local multi-session guard failed open",
                },
                sys.stdout,
            )
            sys.stdout.write("\n")
            return 0
        print(f"local multi-session guard failed: {exc}", file=sys.stderr)
        return 1

    blocked = any(f.level == "BLOCK" for f in findings)
    if args.mode == "session-start":
        json.dump(
            {
                "hookSpecificOutput": {
                    "hookEventName": "SessionStart",
                    "additionalContext": report,
                },
                "systemMessage": "local multi-session guard emitted",
            },
            sys.stdout,
        )
        sys.stdout.write("\n")
        return 0
    if blocked and os.environ.get(OVERRIDE_ENV) != "1":
        print(report, file=sys.stderr)
        print(
            f"\n차단 해제는 정말 의도한 경우에만 `{OVERRIDE_ENV}=1`을 붙여 실행하세요.",
            file=sys.stderr,
        )
        return 1
    if args.mode == "check" or blocked:
        print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
