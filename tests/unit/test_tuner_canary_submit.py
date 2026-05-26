"""스펙 012 T021 — git plumbing 후보 구체화 (작업트리 무변경·미푸시·정리)."""

from __future__ import annotations

import subprocess
from pathlib import Path

from auto_invest.tuner.canary_submit import _materialize_candidate_rev


def _git(args, cwd):
    return subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=True, check=True
    ).stdout.strip()


def _init_repo(tmp_path: Path) -> Path:
    _git(["init", "-q"], tmp_path)
    _git(["config", "user.email", "t@t.local"], tmp_path)
    _git(["config", "user.name", "tester"], tmp_path)
    (tmp_path / "config").mkdir()
    f = tmp_path / "config" / "judgment_tunables.toml"
    f.write_text("[daily_summary]\nmax_tokens = 700\n", encoding="utf-8")
    _git(["add", "."], tmp_path)
    _git(["-c", "commit.gpgsign=false", "commit", "-q", "-m", "init"], tmp_path)
    return tmp_path


def test_materialize_does_not_touch_working_tree(tmp_path: Path):
    repo = _init_repo(tmp_path)
    head_before = _git(["rev-parse", "HEAD"], repo)
    branches_before = _git(["branch", "--list"], repo)
    new_content = "[daily_summary]\nmax_tokens = 560\n"

    candidate_rev, head_rev = _materialize_candidate_rev(
        repo_root=repo,
        target_path="config/judgment_tunables.toml",
        new_content=new_content,
        message="ephemeral candidate",
    )

    # (a) 작업트리 무변경.
    assert _git(["status", "--porcelain"], repo) == ""
    # (b) HEAD·브랜치 무변경, 새 ref 미생성.
    assert _git(["rev-parse", "HEAD"], repo) == head_before
    assert _git(["branch", "--list"], repo) == branches_before
    assert head_rev == head_before
    # (c) 후보 rev 트리에 변경 반영.
    shown = _git(["show", f"{candidate_rev}:config/judgment_tunables.toml"], repo)
    assert "max_tokens = 560" in shown
    # baseline(HEAD) 트리는 원본.
    base = _git(["show", "HEAD:config/judgment_tunables.toml"], repo)
    assert "max_tokens = 700" in base
    # 작업트리 파일도 원본 그대로.
    assert "700" in (repo / "config" / "judgment_tunables.toml").read_text()


def test_candidate_rev_is_dangling_no_ref(tmp_path: Path):
    repo = _init_repo(tmp_path)
    candidate_rev, _ = _materialize_candidate_rev(
        repo_root=repo,
        target_path="config/judgment_tunables.toml",
        new_content="[daily_summary]\nmax_tokens = 560\n",
        message="ephemeral",
    )
    # 어떤 브랜치도 이 커밋을 가리키지 않는다(dangling — push 대상 아님).
    refs = _git(["for-each-ref", "--format=%(objectname)"], repo).splitlines()
    assert candidate_rev not in refs


def test_temp_index_cleaned(tmp_path: Path):
    repo = _init_repo(tmp_path)
    import glob
    import tempfile

    before = set(glob.glob(tempfile.gettempdir() + "/tuner-canary-idx-*"))
    _materialize_candidate_rev(
        repo_root=repo,
        target_path="config/judgment_tunables.toml",
        new_content="[daily_summary]\nmax_tokens = 560\n",
        message="ephemeral",
    )
    after = set(glob.glob(tempfile.gettempdir() + "/tuner-canary-idx-*"))
    assert after == before  # 임시 인덱스 디렉터리 정리됨
