---
name: "handoff"
description: "Refresh the cross-session handoff so the next session starts from truth. Updates HANDOFF.md (the main-branch entry point) — especially the '한눈 요약표' rows (last main commit, tests, lint, released specs, open PRs) and the latest-milestone section — then commits and pushes. Use at the end of an instruction once work is merged/pushed, or whenever HANDOFF.md has drifted from reality. The recurring 'history confusion' failure is caused by a stale HANDOFF; this is the fix."
argument-hint: "optional: a one-line note on what this session accomplished"
metadata:
  author: "auto-invest"
  source: "in-house session-lifecycle tooling"
user-invocable: true
disable-model-invocation: false
---

# /handoff — refresh cross-session handoff state

## User Input

```text
$ARGUMENTS
```

The next session's entire picture of "what is going on" comes from `HANDOFF.md`
plus the live git hooks. When `HANDOFF.md` drifts from `main`, every following
session starts confused. This skill closes the loop: reconcile, edit, push.

Respond to the operator in **Korean** (CLAUDE.md 규칙 1). Plain Korean, no
unexplained English/abbreviations (규칙 2).

## Steps

1. **Gather ground-truth first** (do not write from memory):
   ```bash
   git fetch origin
   git log origin/main -10 --pretty='%h %s'   # real main tip + recent merges
   git log HEAD -10 --pretty='%h %s'          # this session's commits
   git status --porcelain
   ```
   - Open PRs: `mcp__github__list_pull_requests owner=jinooaction repo=claude state=open`.
   - Tests + lint (so the summary table is honest):
     ```bash
     uv run pytest -q
     uv run ruff check src tests
     ```

2. **Update `HANDOFF.md`** (main-branch entry point). At minimum refresh the
   **한눈 요약표** rows so they match step 1 exactly:
   - `마지막 main 커밋` → real `origin/main` tip (`%h %s`).
   - `main 테스트` → real pass/skip count from pytest.
   - `main 린트` → ruff result.
   - `출시 완료 스펙` / `골격 스펙` → reflect any newly-merged spec.
   - `활성 작업` → what is actually in-flight now.
   Also update the "최근 마일스톤" section if this session shipped something,
   and the "현재 main 상태" bullet list. Add stale historical handoffs to the
   "과거 인수인계 파일" list rather than deleting them.

3. **New milestone file (only when warranted).** If this session completed a
   spec or a significant operational change, create `HANDOFF-<NNN>-<SLUG>.md`
   following the existing numbering and the structure of the most recent one,
   then add it to HANDOFF.md's historical list and point the "최근 마일스톤"
   section at it. Do NOT spawn a new file for routine work — edit HANDOFF.md.

4. **Constitution / workflow version drift.** If `CLAUDE.md` or the constitution
   version changed this session, update the HANDOFF rows that cite the version
   (`헌법`, `운영자 응대 정책`) so they match.

5. **Commit and push** (descriptive message; never `--no-verify`):
   ```bash
   git add HANDOFF.md HANDOFF-*.md
   git commit -m "docs(handoff): refresh cross-session state — <one line>"
   git push -u origin <current-branch>   # retry 4× w/ backoff on network error
   ```
   Do NOT push to `main` directly. If the changes belong on an open PR's
   branch, push there; if `HANDOFF.md` itself should reach `main`, that lands
   through the normal PR + autonomous-merge channel (CLAUDE.md 규칙 3).

## Report (Korean, concise)

- HANDOFF.md에서 갱신한 항목 (특히 요약표의 어떤 행이 어떻게 바뀌었는지).
- 새 HANDOFF-NNN 파일을 만들었으면 그 이름과 이유.
- 푸시한 브랜치 + 커밋 해시.
- 다음 세션이 이어받을 한 줄 요약.
