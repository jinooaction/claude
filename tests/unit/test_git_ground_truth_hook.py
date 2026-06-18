from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_hook():
    hook_path = Path(__file__).resolve().parents[2] / ".codex" / "hooks" / "git_ground_truth.py"
    spec = importlib.util.spec_from_file_location("git_ground_truth_hook", hook_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_session_start_context_is_capped_and_actionable(tmp_path, monkeypatch):
    hook = _load_hook()
    monkeypatch.setattr(hook, "REPO", tmp_path)

    (tmp_path / "HANDOFF.md").write_text("# Main handoff\n", encoding="utf-8")
    for idx in range(1, 6):
        (tmp_path / f"HANDOFF-{idx:03d}-TOPIC.md").write_text(
            f"# Handoff {idx}\n",
            encoding="utf-8",
        )

    dirty_rows = "\n".join(f" M file_{idx}.py" for idx in range(10))

    def fake_git(*args: str) -> str:
        if args == ("rev-parse", "--abbrev-ref", "HEAD"):
            return "Codex/example"
        if args == ("log", "-1", "--pretty=%h %s"):
            return "abc1234 current work"
        if args == ("status", "--porcelain"):
            return dirty_rows
        if args == ("rev-list", "--left-right", "--count", "origin/main...HEAD"):
            return "2 5"
        if args[:2] == ("log", "origin/main"):
            return "\n".join(f"  main{i} merged {i}" for i in range(6))
        if args[:2] == ("log", "HEAD"):
            return "\n".join(f"  head{i} local {i}" for i in range(5))
        return ""

    monkeypatch.setattr(hook, "_git", fake_git)

    text = hook._build()

    assert "current branch : Codex/example" in text
    assert "vs origin/main : 5 ahead, 2 behind" in text
    assert "working tree   : 10 changed path(s)" in text
    assert "... 4 more path(s)" in text
    assert "HANDOFF.md: Main handoff" in text
    assert "HANDOFF-005-TOPIC.md: Handoff 5" in text
    assert "HANDOFF-004-TOPIC.md: Handoff 4" in text
    assert "HANDOFF-003-TOPIC.md: Handoff 3" in text
    assert "HANDOFF-002-TOPIC.md" not in text
    assert "run /sync before PR, merge, deploy, or remote-branch decisions" in text
    assert len(text.splitlines()) <= 40


def test_clean_worktree_omits_dirty_sample(tmp_path, monkeypatch):
    hook = _load_hook()
    monkeypatch.setattr(hook, "REPO", tmp_path)

    def fake_git(*args: str) -> str:
        responses = {
            ("rev-parse", "--abbrev-ref", "HEAD"): "main",
            ("log", "-1", "--pretty=%h %s"): "abc1234 current work",
            ("status", "--porcelain"): "",
            ("rev-list", "--left-right", "--count", "origin/main...HEAD"): "0 0",
        }
        if args[:2] == ("log", "origin/main"):
            return "  abc1234 current work"
        return responses.get(args, "")

    monkeypatch.setattr(hook, "_git", fake_git)

    text = hook._build()

    assert "working tree   : clean" in text
    assert "dirty sample" not in text
