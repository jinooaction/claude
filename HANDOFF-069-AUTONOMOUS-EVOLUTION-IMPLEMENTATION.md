# HANDOFF 069 — 스펙 067 영구 자율 성장 루프 구현 (2026-06-29 KST)

main 베이스라인: `424a70e`(PR #404). 스펙 067이 설계·프레이밍 단계에서 실제 read-only
운영 루프로 넘어왔다. 이제 루프는 이미 발행된 sidecar와 repo 문서를 읽어 전 영역 고레버리지
돌파 후보, 안전한 실험 계획, 학습 장부, 최신 실행 보고서를 자동으로 만든다.

## 무엇이 바뀌었나

- `src/auto_invest/analytics/evolution_loop.py`: 증거 표면, 도메인 registry, 후보 점수화,
  실험 계획, 승격 결정, 학습 장부, markdown/JSON rendering을 추가했다.
- `scripts/evolution_loop_probe.py`: workflow용 `--manifest`, JSON/text 출력, 최신 실행 요약,
  `learning_ledger.json`, `candidate_backlog.json` 산출을 추가했다.
- `auto-invest evolution-scan`: 같은 read-only scan을 로컬 CLI로 실행할 수 있게 했다.
- `.github/workflows/autonomous-evolution-loop.yml`: 매일 08:30 UTC와 main push 때 sidecar를 읽고
  `automation/autonomous-evolution-last-run`에 최신 결과를 발행한다.
- `pipeline_liveness`: `autonomous-evolution` sidecar를 비치명(non-critical) 생존 감시 대상으로
  등록했다.
- `safety.command_registry`: `evolution-scan`을 A0(read-only) 안전 정책으로 등록했다.
- `specs/067-autonomous-evolution-loop/tasks.md`: T001~T032를 완료 처리했다. T033은 이 handoff
  refresh와 머지로 닫힌다.

## 첫 실행 증거

PR #404가 main에 머지된 뒤 `autonomous-evolution-loop` workflow가 push 트리거로 실행되어
`automation/autonomous-evolution-last-run`을 발행했다.

- run_id: `28329967896`
- commit: `424a70e16a442b0bde54db2da47b3d69ab14e78c`
- overall_status: `ok`
- stale 또는 missing evidence: 없음
- operator review 후보: 없음
- 상위 후보:
  1. micro GTAA 의도 손익 재검토와 대체 전략 연구
  2. 돈 경로 준비도와 기존 게이트 정렬
  3. 비상관 포트폴리오 후보 비교력 강화
- 안전 문구: 주문, 자본, whitelist/caps, live 전략은 변경하지 않았음.

다음 세션은 `git show origin/automation/autonomous-evolution-last-run:LAST_RUN.md`를 우선 읽으면
루프의 최신 후보와 학습 장부 상태를 한 번에 확인할 수 있다.

## 안전 경계

- 위험 등급: 2(운영 자동화·sidecar·CLI 추가)
- 실제 주문 실행: 없음
- broker API 호출: 없음
- micro GTAA 재무장: 없음
- 자본 증액, 허용 종목 확대, 포지션 한도 완화, live 전략 교체: 없음
- 비밀값 출력: 마스킹/거부 테스트 추가
- workflow 실패 전파: 모든 shell step을 `set -euo pipefail`로 고정
- 검증된 전략 후보도 스펙 055 재지정 게이트 밖에서 live 전략으로 승격하지 않는다.
- 자본 확대 후보도 스펙 050 자본 사다리 밖에서 처리하지 않는다.

## 검증

PR #404 머지 전:

- `uv run pytest` → 2310 passed, 4 skipped
- `uv run ruff check src tests` → All checks passed
- `uv run python scripts/check_handoff_facts.py` → OK
- `uv run python scripts/agent_harness_probe.py --strict` → OK (14/14)
- `git diff --check` → clean
- `uv run python scripts/check_pr_quality_gate.py --template .github/pull_request_template.md` → OK
- PR #404 품질 관문 → success, mergeable `CLEAN`, merge 방식으로 main에 병합

handoff 갱신 전 main 기준:

- `uv run ruff check src tests` → All checks passed
- `uv run pytest -q` → stale `HANDOFF.md` 때문에 하네스 2건만 실패. 이 handoff 갱신은
  `마지막 main 커밋` 행과 스펙 067 상태를 바로잡아 그 원인을 제거한다.

## 다음 세션 한 줄

스펙 067은 구현 완료다. 다음 세션은 `automation/autonomous-evolution-last-run` sidecar에서 최신
고레버리지 후보와 학습 장부를 읽고, 후보를 새 주문·자본 변경으로 직접 실행하지 말고 기존 스펙
055 재지정 게이트와 스펙 050 자본 사다리로만 승격시킨다.
