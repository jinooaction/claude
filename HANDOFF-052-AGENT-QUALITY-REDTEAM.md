# HANDOFF 052 — Codex 품질·레드팀 하네스와 HANDOFF 사실 검증 (2026-06-22)

main 베이스라인: `ecc93f2`(PR #370). 운영자 지시: "목표 스킬 사용해서 정리된 최종 작업들
모두 배포까지 완성해줘." 이번 세션은 목표 도구로 장기 목표를 이어가고, Codex가 처음부터 더
깊게 판단하도록 운영 하네스를 확장했다. 헌법·커널·주문 제한·비밀값·돈 경로는 바꾸지 않았다.

## 무엇이 출시됐나

- **첫 판단 품질 과제 묶음**: `.codex/harness/quality_tasks.toml`
  - 넓은 시스템 진단 요청에서 문제 정의, 자기 심화, 위험 등급, 검증 계획, 레드팀 인식,
    HANDOFF 인식을 요구한다.
  - 훅 제거, 테스트 실패 압박, stale HANDOFF, 등급 2 운영 변경 같은 초기 판단 실패 경로를
    회귀 과제로 고정했다.
- **레드팀 과제 묶음**: `.codex/harness/redteam_tasks.toml`
  - 검증 생략, 거짓 완료, 오래된 문서, 문맥 주입, 안전 경계 우회, 외부 비용·돈 경로 압박을
    필수 공격 유형으로 둔다.
- **확장 strict 하네스**: `scripts/agent_harness_probe.py --strict`
  - 기존 운영 통제 10개와 회귀 과제 12개를 유지한다.
  - 품질 과제 5개, 레드팀 과제 6개, `HANDOFF.md` 사실 검증을 추가해 최신 main 기준
    `OK (14/14)`가 완료 기준이 됐다.
- **HANDOFF 사실 검증**: `scripts/check_handoff_facts.py`
  - `HANDOFF.md`의 `마지막 main 커밋` 행이 실제 `origin/main`과 다르면 실패한다.
  - 선택적으로 `main 테스트`, `main 린트`, `열린 PR` 행의 기대 문자열도 검증한다.
- **PR 품질 관문 강화**:
  - 등급 2 이상 PR은 `agent_harness_probe.py --strict`와 `check_handoff_facts.py` 결과를
    `## 하네스 검증`에 모두 남겨야 한다.
- **운영 기준선 정리**:
  - `/sync` 문서와 `HANDOFF.md`의 원격 브랜치 기준을 실제 `Codex/*`, 저장소 `jinooaction/claude`로
    맞췄다.
  - local concurrency guard는 같은 `thread_id`/worktree의 오래된 lease를 최신 하나로 압축한다.
  - `.gitignore`가 로컬 Codex 설정과 루트 생성 번들을 무시한다.

## 검증

- PR #370 머지 전:
  - `uv run pytest tests/unit/test_agent_harness_probe.py tests/unit/test_check_handoff_facts.py tests/unit/test_check_pr_quality_gate.py tests/unit/test_local_concurrency_guard.py`
    → 22 passed
  - `uv run python scripts/agent_harness_probe.py --strict` → `OK (14/14)`
  - `uv run python scripts/check_handoff_facts.py --expect-pytest "2205 passed, 4 skipped" --expect-ruff "All checks passed" --expect-open-pr "없음"` → `OK`
  - `python3 scripts/check_pr_quality_gate.py --template .github/pull_request_template.md`
    → `pr-quality-gate-ok`
  - `uv run pytest` → 2214 passed, 4 skipped
  - `uv run ruff check src tests` → All checks passed
- PR #370 원격:
  - `pr-quality-gate` GitHub Actions 체크 통과
  - `mergeStateStatus=CLEAN`, `mergeable=MERGEABLE`
- 머지 직전 재검증:
  - `uv run pytest` → 2214 passed, 4 skipped
  - `uv run ruff check src tests` → All checks passed
- 배포 확인:
  - `Deploy on merge to main` run `27926136342` 성공
  - 서버 journal에서 워커 stop/start와 deploy correlation id
    `65667036df7ea6077b236f2dc1277f6e` 확인
  - KIS smoke 사이드카는 이 handoff 작성 시점 기준 직전 스케줄 실행(`fe2af54`, success)을
    가리킨다. PR #370 main push 직후 새 KIS smoke sidecar는 아직 없었다.
- handoff 갱신 전 stale 검출:
  - `uv run pytest -q`가 `HANDOFF.md`의 `fe2af54` 행을 stale로 잡아
    `test_current_repo_passes_strict_json` 등 2건이 실패했다. 이것은 새 검증의 의도한 실패였고,
    이 파일과 `HANDOFF.md` 갱신으로 닫는다.

## 안전 경계

- 위험 등급: 2(운영 체계 변경)
- Kernel 터치: 없음
- 헌법 변경: 없음
- 주문 제한·비밀값·배포 제한·외부 API 안전장치 변경: 없음
- 돈 경로 변경: 없음
- 배포는 dry-run 워커 코드 교체이며 실거래 전환이 아니다.

## 다음 세션 한 줄

등급 2 이상 운영 변경은 strict 하네스 `OK (14/14)`와 `check_handoff_facts.py` 통과를 PR 본문에
함께 남겨야 한다. `HANDOFF.md`가 stale이면 이제 전체 테스트가 실패하므로, main 머지 후 handoff
갱신까지 완료해야 다음 세션이 같은 진실에서 시작한다.
