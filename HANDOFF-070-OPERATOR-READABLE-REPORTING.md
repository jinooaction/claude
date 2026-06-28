# HANDOFF 070 — 운영자가 이해 가능한 완료 보고 강제 (2026-06-29 KST)

main 베이스라인: `c4400b7`(PR #406). 운영자가 "그래서 뭘 했다는 거야?"라고 다시 물어야 하는
완료 보고를 시스템 실패로 보고, Codex 운영 규칙과 하네스에 재발 방지를 넣었다.

## 무엇이 바뀌었나

- `AGENTS.md`: 최종 답변은 PR 번호나 커밋 해시가 아니라 실제 운영 상태 변화부터 말해야 한다.
  이후 무엇을 만들었는지, 돈 경로·자동화·안전 경계·다음 세션 행동에 어떤 의미가 있는지,
  무엇으로 확인했는지, 남은 위험은 무엇인지 쉬운 한글로 분리해야 한다.
- `.codex/quality-gate.md`: 완료 전 "운영자 이해 가능 보고" 점검 항목을 추가했다.
- `.codex/harness/quality_tasks.toml`: `QUALITY-006`을 추가해 "운영자가 완료 보고를 이해하지 못함"
  상황을 첫 판단 품질 과제로 고정했다.
- `scripts/agent_harness_probe.py`: 필수 첫 판단 품질 범주에 `operator_readability`를 추가했고,
  `AGENTS.md`와 품질 관문 문서가 이 보고 규칙을 포함하는지 검사한다.
- `tests/unit/test_agent_harness_probe.py`: 새 필수 범주에 맞춰 회귀 테스트를 갱신했다.

## 운영상 의미

- 앞으로 큰 작업 후 보고는 "무엇이 현실에서 달라졌는가"가 먼저 나와야 한다.
- 테스트 수, PR 번호, 커밋 해시, sidecar run id, 배포 run id는 증거일 뿐이다. 그 증거가
  운영자에게 어떤 의미인지 설명하지 않으면 완료 보고 실패로 본다.
- 등급 2 이상 변경, 돈 경로, 안전 경계, 자동화, 인계 변경은 전문 용어를 그대로 던지지 않고
  쉬운 한글 설명을 붙여야 한다.

## 안전 경계

- 위험 등급: 2(운영 규칙·품질 관문·하네스 변경)
- 실제 주문 실행: 없음
- broker API 호출: 없음
- 자본 증액, 허용 종목 확대, 포지션 한도 완화, live 전략 교체: 없음
- 헌법, 커널 목록, 주문 제한, 비밀값, 감사 로그 변경: 없음
- 기존 검증·PR 품질 관문·HANDOFF 사실검증은 유지하고, 보고 이해 가능성 요구만 추가했다.

## 검증

PR #406 머지 전:

- `uv run pytest` → 2310 passed, 4 skipped
- `uv run ruff check src tests` → All checks passed
- `uv run ruff check scripts/agent_harness_probe.py tests/unit/test_agent_harness_probe.py` → All checks passed
- `uv run python scripts/check_handoff_facts.py` → OK
- `uv run python scripts/agent_harness_probe.py --strict` → OK (14/14), 첫 판단 품질 과제 6개와
  `operator_readability` 포함 확인
- `git diff --check` → clean
- `uv run python scripts/check_pr_quality_gate.py --template .github/pull_request_template.md` → OK
- PR #406 품질 관문 → success, mergeable `CLEAN`, merge 방식으로 main에 병합

handoff 갱신 전 main 기준:

- `uv run ruff check src tests` → All checks passed
- `uv run pytest -q` → stale `HANDOFF.md` 때문에 하네스 2건만 실패. 이 handoff 갱신은
  `마지막 main 커밋` 행과 운영자 응대 정책 상태를 바로잡아 그 원인을 제거한다.

## 다음 세션 한 줄

완료 보고는 이제 "증거 나열"이 아니라 "운영자가 바로 이해할 수 있는 실제 상태 변화 설명"이어야
한다. 큰 작업을 끝낼 때는 의미, 안전 경계, 검증, 남은 위험을 먼저 설명하고 PR 번호와 커밋은
증거로 붙인다.
