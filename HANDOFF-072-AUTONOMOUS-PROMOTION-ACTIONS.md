# HANDOFF 072 — 자율 승격 실행 루프 자동화 (2026-06-29 KST)

main 베이스라인: `27da8b4`(PR #410). 스펙 068의 read-only 승격 판단을 promotion 전용 forward paper 등록 큐와 hardened canary 제출 큐로 자동 연결하는 스펙 069를 출시했다.

## 무엇이 바뀌었나

- `specs/069-autonomous-promotion-actions/`: 목표, 비목표, 안전 경계, 데이터 모델, 계약, quickstart, tasks를 남겼다.
- `src/auto_invest/analytics/promotion_actions.py`: promotion summary를 읽어 forward 등록과 canary 제출 다음 상태를 결정론적으로 계산한다.
- `scripts/promotion_action_probe.py`와 `auto-invest promotion-actions`: 로컬·workflow에서 같은 action state를 재현한다.
- `automation/promotion-forward-registry.json`, `automation/promotion-canary-submissions.json`: tracked fallback 상태 파일을 추가했다.
- `.github/workflows/autonomous-promotion-actions.yml`: 매일 09:00 UTC와 관련 main push 때 action sidecar를 발행하고, 상태 변경은 PR 경로로 남긴다.
- `.github/workflows/promotion-forward-tracks.yml`: action sidecar의 next registry를 우선 읽고, 등록된 후보를 `--mode paper`로만 forward 검증한다.
- `.github/workflows/promotion-canary-submissions.yml`: action sidecar의 next submissions를 우선 읽고, 등록된 후보를 `canary-portfolio` hardened canary로만 검증한다.
- `promotion_loop.py`: `promotion-forward`와 `promotion-canary` sidecar를 증거로 읽어 후보 단계를 다음 scan에서 자동 상승시킨다.
- `pipeline_liveness`: `autonomous-promotion-actions`, `promotion-forward`, `promotion-canary`를 non-critical 감시 대상으로 등록했다.

## 운영상 의미

- 이제 루프는 `후보 발굴 -> 승격 분류 -> 검증 큐 등록 -> forward paper/canary 실행 -> 다음 승격 분류`까지 닫혔다.
- 후보가 `promotion_evidence.forward_track`을 제공하고 `FORWARD_REGISTRATION_READY`가 되면 promotion forward registry에 자동 등록된다.
- 후보가 `promotion_evidence.canary_track`을 제공하고 `CANARY_CANDIDATE`가 되면 promotion canary submission queue에 자동 제출된다.
- 현재 실제 후보들은 모두 `BACKTEST_REQUIRED`라서 첫 action 실행은 등록·제출 0건이었다. 이것은 정상이다. 검증 가능한 track 설정과 증거가 생기면 다음 실행에서 자동 등록된다.

## 첫 실행 증거

- `Autonomous promotion actions` run `28333113593`: success, commit `27da8b46eafb0a2abdc20399c9f65b424637e13b`
- sidecar: `automation/autonomous-promotion-actions-last-run`
- action summary: `overall_status=ok`, `registered=0`, `submitted=0`, `blocked=0`
- `Promotion forward tracks` run `28333113584`: success, `track_count=0`, paper-only sidecar 발행
- `Promotion canary submissions` run `28333113596`: success, `pending_submission_count=0`, canary-only sidecar 발행
- `Autonomous promotion loop` run `28333113599`: success, 최신 후보는 여전히 모두 `BACKTEST_REQUIRED`

## 배포와 smoke

- `Deploy on merge to main` run `28333113591`: success
- `KIS smoke (autonomous)` run `28333113580`: success
- KIS smoke commit: `27da8b46eafb0a2abdc20399c9f65b424637e13b`
- `key_valid=true`, live broker smoke 4건 통과
- 배포는 dry-run worker 코드 반영이다. 실거래 전환이 아니다.

## 안전 경계

- 위험 등급: 2(운영 자동화 변경)
- 실제 주문 실행: 없음
- 신규 action workflow의 SSH/KIS 사용: 없음
- promotion forward workflow: `--mode paper`만 사용, `--mode live`/`--confirm-live` 없음
- promotion canary workflow: `canary-portfolio`만 사용, `--mode live`/`--confirm-live` 없음
- 자본 증액, 허용 종목 확대, 포지션 한도 완화, live 전략 교체, live sentinel 변경: 없음
- 헌법, 커널 목록, 주문 제한, 비밀값, 감사 로그 변경: 없음
- 자본과 전략 승격은 계속 스펙 050 자본 사다리와 스펙 055 재지정 게이트만 담당한다.

## 검증

PR #410 머지 전:

- focused pytest 48 통과
- `uv run pytest` → 2333 passed, 4 skipped
- `uv run ruff check src tests` → All checks passed
- `git diff --check` → clean
- touched workflow Ruby YAML parse → OK
- `promotion_action_probe.py` artifact smoke → success
- `auto-invest promotion-actions --format json` CLI smoke → success
- `uv run python scripts/check_handoff_facts.py` → OK
- `uv run python scripts/agent_harness_probe.py --strict` → OK (14/14)
- PR 품질 관문 → success, mergeable, merge 방식으로 main에 병합

handoff 갱신 기준:

- `uv run ruff check src tests` → All checks passed
- `uv run pytest -q` → 2333 passed, 4 skipped
- `uv run python scripts/check_handoff_facts.py` → OK
- `uv run python scripts/agent_harness_probe.py --strict` → OK (14/14)

## 다음 세션 한 줄

자율 승격 루프는 이제 판단만 하지 않는다. 안전한 후보만 promotion 전용 forward paper와 hardened canary 검증 큐에 자동으로 올리고, 실제 돈은 여전히 기존 자본 사다리와 재지정 게이트 밖으로 나가지 않는다.
