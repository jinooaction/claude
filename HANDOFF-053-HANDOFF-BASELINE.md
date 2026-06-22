# HANDOFF 053 — HANDOFF-only merge 기준선 보정 (2026-06-22)

main 베이스라인: `119ad4a`(PR #372). PR #370에서 `HANDOFF.md` 사실 검증을 도입한 뒤,
PR #371 handoff-only merge가 자기 자신의 merge commit 해시를 미리 쓸 수 없어 strict 하네스가
다시 stale로 판정하는 재귀 문제가 드러났다. PR #372는 이 결함을 보정했다.

## 무엇이 출시됐나

- `scripts/check_handoff_facts.py`가 기준선을 두 단계로 본다.
  - 일반 경우: `origin/main` 최신 커밋이 `HANDOFF.md`의 `마지막 main 커밋` 행과 일치해야 한다.
  - 예외 경우: 최신 `origin/main`이 `.md` 또는 `specs/`만 바꾼 handoff-only merge이면, 그 merge의
    첫 번째 부모도 유효한 기준선으로 인정한다.
- 일반 코드 merge의 stale HANDOFF 실패는 유지한다.
- handoff-only merge 예외는 `tests/unit/test_check_handoff_facts.py`에 고정했다.

## 검증

- PR #372 머지 전:
  - `uv run pytest tests/unit/test_check_handoff_facts.py tests/unit/test_agent_harness_probe.py`
    → 13 passed
  - `uv run python scripts/check_handoff_facts.py --expect-pytest "2214 passed, 4 skipped" --expect-ruff "All checks passed"`
    → `OK`
  - `uv run python scripts/agent_harness_probe.py --strict` → `OK (14/14)`
  - `uv run ruff check src tests scripts/check_handoff_facts.py scripts/agent_harness_probe.py`
    → All checks passed
- 머지 직전:
  - `uv run pytest -q` → 2215 passed, 4 skipped
  - `uv run ruff check src tests` → All checks passed
- 배포 확인:
  - `Deploy on merge to main` run `27926514587` 성공
  - 서버 journal에서 워커 stop/start와 deploy correlation id
    `68e0d2e01c439296086067f63af89c65` 확인

## 안전 경계

- 위험 등급: 2(운영 체계 변경)
- Kernel 터치: 없음
- 헌법 변경: 없음
- 주문 제한·비밀값·배포 제한·돈 경로 변경 없음
- 배포는 dry-run 워커 코드 교체이며 실거래 전환이 아니다.

## 다음 세션 한 줄

`HANDOFF.md` 사실 검증은 일반 코드 merge의 stale 상태를 계속 실패로 잡는다. 단, handoff-only
merge 직후에는 직전 main 기준선을 정상으로 본다. 이 예외 덕분에 handoff 갱신 PR이 자기 merge
해시를 미리 알 수 없는 구조에서도 strict 하네스가 재귀 실패하지 않는다.
