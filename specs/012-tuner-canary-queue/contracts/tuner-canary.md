# Contract — Tuner ↔ Hardened-Canary (internal)

이 기능은 외부 API 를 추가하지 않는다. 계약은 (a) 튜너 내부 모듈 경계,
(b) 스펙 007 캐너리 소비 계약, (c) git plumbing 명령, (d) 감사 이벤트 스키마다.

## C1. candidate.py — 후보 구체화

```python
def build_canary_candidate(c: Classification, *, tunables_path: Path) -> CanaryCandidate | None:
    """L2/L3 비커널 분류를 캐너리 후보로 구체화. 구체 노브 없으면 None."""
```

- **입력**: `Classification.tier in {"L2","L3"}` 且 비커널. v1 은 `max_tokens_reduce`
  종류만 구체화(그 외는 None → 기존 canary_entered 로그만).
- **출력 불변식**: `old_value != new_value`, `new_value >= 바닥 클램프`.
- **결정성**: 동일 입력 → 동일 출력. LLM·벽시계·난수 미사용.

## C2. canary_submit.py — 캐너리 투입

```python
def submit_to_canary(
    candidate: CanaryCandidate, *,
    repo_root: Path, audit_conn: sqlite3.Connection, session_date: str,
    history_root: Path, run_canary_fn=run_canary,   # 테스트 주입 가능
) -> CanaryValidationResult:
```

- `run_canary_fn` 기본값은 실제 `auto_invest.canary.run.run_canary`; 테스트는 더블 주입.
- **fail-safe**: `latest_dataset_dir(history_root) is None` → `CanaryValidationResult(skipped, no_replay_data)`, 캐너리 미호출.
- **오류 격리**: `run_canary_fn` 예외 또는 `outcome=="in_progress"`/`exit_code==EXIT_INTERNAL`
  → `CanaryValidationResult(internal_error)`. 예외를 호출자로 전파하지 않음.
- **승격 금지**: 반환의 `promoted` 는 항상 False. 배포/승격 이벤트 미발생.

## C3. 캐너리 소비 계약 (스펙 007, 변경 없음 — 소비만)

```python
run_canary(
    CanaryOptions(
        tier=<L2|L3>,
        candidate_rev=<임시 후보 SHA>,
        baseline_rev=<HEAD SHA>,
        replay_inputs=<ReplayWindowInputs>,  # 캐너리 CLI 패턴 재사용
        shock_inputs=None,                   # v1: 충격 생략 가능(또는 합성 충격 주입)
        repo_root=<repo>,
    ),
    audit_conn=<conn>,
) -> CanaryRunOutcome   # outcome ∈ {passed, failed, in_progress}
```

- 캐너리 패키지(`src/auto_invest/canary/`)는 **한 줄도 수정하지 않는다**.
- `CanaryRunOutcome.outcome == "passed"` → 검증 합격. `"failed"` → `failing_metrics` 기록.

## C4. git plumbing 계약 (작업트리 무변경·미푸시)

후보 1건을 임시 인덱스로 구체화:

```
GIT_INDEX_FILE=<tmp> git read-tree HEAD
<blob> = git hash-object -w <임시 변경 파일>
GIT_INDEX_FILE=<tmp> git update-index --add --cacheinfo 100644,<blob>,<target_path>
<tree>   = GIT_INDEX_FILE=<tmp> git write-tree
<commit> = git commit-tree <tree> -p HEAD -m "ephemeral tuner canary candidate"
```

- **불변식**: 실제 인덱스·작업트리·HEAD·브랜치 미변경(임시 인덱스 파일만 사용 후 삭제).
- **불변식**: `git push` 절대 호출하지 않음. ref 생성 안 함(루스 객체만, GC 대상).
- 임시 인덱스 파일은 `finally` 에서 삭제.

## C5. runner.py 배선 (수정)

기존 L2/L3 분기(`canary_entered.append(c)` + `AUTO_TUNED_L2_CANARY_ENTERED` 로그)를:

```python
if c.tier in ("L2", "L3") and not c.kernel_groups:
    cand = build_canary_candidate(c, tunables_path=...)
    if cand is None:
        canary_entered.append(c)              # 기존 동작(구체 노브 없음)
        # AUTO_TUNED_L2_CANARY_ENTERED 유지
        continue
    canary_candidates.append(cand)
    if mode == "apply":
        if _candidate_already_recorded(conn, cand, session_date):
            skipped.append((cand.candidate_id, "already_validated_this_session")); continue
        append(conn, AutoTunedCanaryCandidatePayload(...))
        result = submit_to_canary(cand, ...)
        canary_validations.append(result)
        append(conn, AutoTunedCanaryValidatedPayload(... promoted=False ...))
```

- dry-run: `build_canary_candidate` 까지만 → `canary_candidates` 채우고 감사·캐너리 없음.
- L4: 기존 `awaiting_human_merge` 분기 그대로(캐너리 투입 안 함).

## C6. 리포트 계약 (`report.py`, `auto-invest tune` 출력)

- 튜너 리포트 JSON 에 `canary_candidates`·`canary_validations` 섹션 추가.
- 합격 후보 옆에 반드시 표식: `"promotion": "operator-gated (spec 006); NOT auto-promoted"`.
- `auto-invest tune` 사람용 출력에 "캐너리 후보 N건 / 합격 M / 불합격 K / 건너뜀 S
  — 라이브 미승격(운영자 게이트)" 요약 줄.
