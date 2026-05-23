---
name: "deploy-status"
description: "Check whether the latest merge to main actually deployed to the live (dry-run) worker, from inside this container. Deploy is push-triggered (deploy-on-merge.yml on push:main), so it does NOT appear in any PR's check_runs — this skill points at the surfaces that DO show it from here (the main commit's check runs via GitHub MCP, the kis-smoke sidecar branch) and names the operator-only surfaces (Actions Summary, server audit_log) that this container cannot reach. Use after an autonomous merge, or when asked 'did it deploy / is the worker on the new code'."
argument-hint: "optional: a main commit SHA to check (defaults to origin/main tip)"
metadata:
  author: "auto-invest"
  source: "in-house session-lifecycle tooling"
user-invocable: true
disable-model-invocation: false
---

# /deploy-status — did the latest merge reach the live worker?

## User Input

```text
$ARGUMENTS
```

Deploy is **push-triggered**: `deploy-on-merge.yml` fires on `push:main`, SSHes
to the Vultr host, and runs the spec 006 safety state machine
(`auto-invest deploy --branch main`). Two consequences shape what you can check
**from inside this container**:

1. The deploy run is attached to the **`main` commit**, not to any PR. So
   `pull_request_read` check runs will NOT show it — you must look at the
   commit's checks instead.
2. The authoritative evidence (Actions run Summary, the server's `audit_log`
   `DEPLOY_*` rows) lives on surfaces this container cannot reach (no `gh`, no
   SSH, GitHub-only egress). Be honest about that boundary — report what you
   verified vs. what only the operator can confirm.

Also remember: **deploy ≠ live money.** The worker is `AUTO_INVEST_MODE=dry-run`;
deploy swaps code and restarts, it never routes real orders. `live` is an
operator-only toggle this pipeline never touches. Say so if it is relevant.

Respond to the operator in **Korean** (CLAUDE.md 규칙 1).

## Steps

1. **Identify the target commit.** Use `$ARGUMENTS` if a SHA was given,
   otherwise the real tip of `main`:
   ```bash
   git fetch origin main
   git log origin/main -1 --pretty='%H %h %s'
   ```
   If the merge only touched paths in `deploy-on-merge.yml`'s `paths-ignore`
   (`**.md`, `specs/**`, `.verify/**`, `.trigger/**`), the workflow was skipped
   by design — say "배포 트리거 없음(문서/스펙만 변경)" and stop.

2. **Check the main commit's CI/deploy checks via GitHub MCP** (the only deploy
   surface reachable here). Prefer:
   - `mcp__github__get_commit` with `owner=jinooaction repo=claude sha=<the SHA>`
     and inspect the returned status / check-run info for the
     "Deploy on merge to main" workflow's conclusion.
   - If you need the workflow run distinct from PR-CI, `mcp__github__list_commits`
     on `main` confirms the SHA and ordering.
   Report the deploy check's state: success / failure / in-progress / not-found.

3. **Cross-check the KIS smoke sidecar.** The autonomous KIS regression writes a
   one-line diagnostic to a sidecar branch on every run (and on main push):
   ```bash
   git show origin/automation/kis-smoke-last-run:LAST_RUN.md
   ```
   A recent `smoke_state=success` / `key_valid=true` after the merge is
   corroborating evidence the post-merge worker is healthy.

4. **Name the operator-only confirmation** (do not pretend you checked it):
   - GitHub Actions → "Deploy on merge to main" 실행 **Summary** (즉시 결과).
   - 서버 `audit_log` 의 `DEPLOY_STARTED` / `DEPLOY_COMPLETED` /
     `DEPLOY_FAILED` / `DEPLOY_ROLLED_BACK` 행을 `deploy correlation_id` 로 조인
     (`deploy/README.md` § 4). 장중 머지였다면 `market_hours_guard`(헌법 VIII.A)
     가 "장중 연기"로 끝내고 `auto-invest-deploy.timer` 가 장 마감 후 올린다 —
     실패가 아니라 안전망 동작임.

## Report (Korean, concise)

- 대상 `main` 커밋 (`%h %s`).
- 컨테이너에서 확인된 것: 머지 커밋의 "Deploy on merge to main" 체크 상태 +
  kis-smoke 사이드카 최신 상태.
- 컨테이너에서 확인 불가한 것(운영자 확인 필요): Actions Summary, 서버 audit_log.
- 한 줄 결론: 배포가 (a) 성공 반영됨 / (b) 진행 중 / (c) 장중 연기(타이머 대기) /
  (d) 실패 → 다음 행동. 필요하면 "배포 ≠ 실거래(dry-run)" 한 줄 덧붙임.
