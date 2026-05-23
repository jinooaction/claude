---
name: "sync"
description: "Reconcile this session with reality: fetch origin, list remote claude/* branches and open PRs, locate the live HANDOFF, and report where current work actually stands. Run at session start (or any time you are unsure what is merged / in-flight). This is the network half of the start-up discovery; the local half is emitted automatically by the git_ground_truth SessionStart hook."
argument-hint: "(no args)"
metadata:
  author: "auto-invest"
  source: "in-house session-lifecycle tooling"
user-invocable: true
disable-model-invocation: false
---

# /sync — reconcile session with remote ground-truth

You are about to figure out **what is actually merged and what is in-flight**,
so you do not invent a new branch off `main` or trust a stale "active feature"
line. The `git_ground_truth` SessionStart hook already printed the LOCAL state
(current branch, HEAD, HANDOFF list, HEAD vs `origin/main`). This skill adds the
NETWORK state that a hook must not block on.

Respond to the operator in **Korean** (CLAUDE.md 규칙 1).

## Steps

1. **Fetch.** Refresh remote refs (retry up to 4× with backoff on network error,
   per the repo's git policy):
   ```bash
   git fetch origin
   ```

2. **Remote in-flight branches.** List every `claude/*` branch on origin —
   in-flight work lives here:
   ```bash
   git ls-remote --heads origin 'claude/*' | awk '{print $2}'
   ```

3. **Open PRs (single source of truth for in-flight state).** Call the GitHub
   MCP tool — do NOT shell out to `gh` (unavailable here):
   - `mcp__github__list_pull_requests` with `owner=jinooaction repo=claude state=open`
   For each open PR note number, title, head branch, draft flag, and
   `mergeable_state` (use `mcp__github__pull_request_read` if you need detail).

4. **Locate the live HANDOFF.** The highest-numbered `HANDOFF-NNN.md` on the
   active branch is usually the live work pointer. If an open PR points at a
   branch other than the one you are on, read that branch's HANDOFF without
   checking out:
   ```bash
   git show origin/<branch>:HANDOFF-<NNN>.md   # or :HANDOFF.md
   ```

5. **Reconcile `main`.** Confirm the real tip of `main` and recent merges:
   ```bash
   git log origin/main -8 --pretty='%h %s'
   ```
   Cross-check this against HANDOFF.md's "한눈 요약표 → 마지막 main 커밋"
   row. If they disagree, HANDOFF.md is stale — say so, and offer to run
   `/handoff` to refresh it.

6. **Decide, do not ask.** Per CLAUDE.md IX.D autonomy: if an open PR + live
   HANDOFF clearly point at the next task, check out that branch
   (`git checkout <branch> && git pull --ff-only`) and continue — do NOT ask
   "what would you like to do?". Only stop to ask if the discovery surfaces a
   genuine ambiguity the HANDOFF does not resolve.

## Report (Korean, concise)

Give the operator a short reconciliation:
- 현재 브랜치 / 실제 `main` 최신 커밋.
- 열린 PR 목록 (번호·제목·머지 가능 상태).
- 원격 `claude/*` 진행 브랜치.
- 어떤 HANDOFF가 살아있는지 + 다음에 할 일 한 줄.
- HANDOFF.md 요약표가 실제 `main` 과 어긋나면 그 사실 + `/handoff` 제안.
