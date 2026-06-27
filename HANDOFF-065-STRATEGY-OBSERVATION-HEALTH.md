# HANDOFF 065 — 전략 검토 관측 품질 오판 보정 (2026-06-27 KST)

main 베이스라인: `d97d6a2`(PR #396). 운영자가 "돈 잃을 게 뻔한 micro GTAA 수행을 왜 해야 하냐"며
전략 고도화 루프를 요구한 뒤, 최신 자율 재지정 sidecar가 정상적인 관측 누적 차이를 후보 품질
장애로 오판하고 있음을 확인했다. 이 작업은 돈 경로를 열지 않고, 전략 검토 루프가 다음 판단을
정확히 하도록 observation-health 판정을 보정한 등급 2 변경이다.

## 무엇이 바뀌었나

- `src/auto_invest/analytics/forward_tournament.py`: `_observation_quality()`가 다음 상태를 구분한다.
  - 모든 후보가 알려져 있고 모두 최소 관측 전(`PREMATURE`)이면 관측 수 차이가 있어도 `OK`.
  - 하나 이상의 후보가 비교 가능(`COMPARABLE`)이고 다른 알려진 후보가 최소 관측 미달이면 `DEGRADED`.
  - 모든 알려진 후보가 비교 가능하면 관측 수 차이가 있어도 `OK`.
  - 판정 누락과 incumbent 누락의 보수적 판정은 기존대로 유지.
- `lagging_keys`, `max_n_obs`, `min_n_obs`는 삭제하지 않는다. 상태가 `OK`여도 운영자가 뒤처진
  후보를 볼 수 있게 한다.
- `tests/unit/test_forward_tournament.py`: all-premature lag `OK`, mixed comparable/premature
  `DEGRADED`, all-comparable lag `OK` 회귀 테스트를 추가했다.
- `tests/integration/test_forward_tournament_probe.py`: 현재 운영 상황과 같은 7트랙 입력
  (대부분 12회, `globalfixed` 9회, 모두 최소 20회 전)이 `observation_health=OK`를 내는지 고정했다.
- `specs/066-strategy-review-observation-health/`: 목표, 비목표, 안전 경계, 데이터 모델, quickstart,
  tasks, requirement checklist를 남겼다.

## 현재 운영 상태

- PR #396은 merge 방식으로 main에 머지됐다. main merge commit은 `d97d6a2`, 구현 commit은
  `f78ac15`다.
- #396 main push의 `Deploy on merge to main` run `28282838560`은 성공했다.
- 최신 reassign sidecar run `28278589509`는 #396 이전 코드로 생성됐다. 그 sidecar의
  `observation_health=DEGRADED`, `lagging_keys=["globalfixed"]`는 stale 판정일 수 있다.
- 다음 reassign 실행에서 모든 후보가 여전히 최소 관측 전이면, 같은 관측 수 차이는 `OK`로
  표시되어야 한다. 하지만 이것은 재지정 허가가 아니다. 아직 비교 가능한 도전자가 없으면
  `HOLD`가 정상 결론이다.
- micro GTAA 실주문 상태는 #394 이후 그대로 `armed:false`, strategy-intent gate `ok=false`,
  `reason=latest_intent_loss`, 실주문 0건이다.
- KIS smoke sidecar 최신 run은 `28281245727` / commit `458c999` / `smoke_state=success`로
  #396 이전 예약 실행이다. #396의 배포 run 자체는 성공했지만, post-merge KIS smoke sidecar는 아직 없다.

## 안전 경계

- 위험 등급: 2(운영 판단 보정)
- 실제 주문 실행: 없음
- micro GTAA 재무장: 없음
- 자본 증액, 허용 종목 확대, live 전략 교체: 없음
- 주문 라우터, 포지션 한도, whitelist, 손실 브레이커, 감사 로그, 비밀값, K1/K2/K4/K5/K6 코드,
  헌법, 커널 목록 변경: 없음
- 이 변경은 "수익 전략을 선택"하지 않는다. true blocker를 "후보 품질 장애"에서 "아직 비교 가능한
  도전자 없음"으로 정확히 드러내는 보정이다.

## 검증

PR #396 머지 전:

- focused tests 70 통과:
  `tests/unit/test_forward_tournament.py`,
  `tests/integration/test_forward_tournament_probe.py`,
  `tests/unit/test_auto_reassign.py`,
  `tests/unit/test_reassign_decide_cli.py`
- `uv run pytest` → 2286 passed, 4 skipped
- `uv run ruff check src tests` → All checks passed
- `uv run ruff check src tests scripts/forward_tournament_probe.py` → All checks passed
- `git diff --check` → clean
- `uv run python scripts/check_pr_quality_gate.py --template .github/pull_request_template.md` → `pr-quality-gate-ok`
- `uv run python scripts/check_pr_quality_gate.py .verify/pr-strategy-observation-health.md` → `pr-quality-gate-ok`
- `uv run python scripts/check_handoff_facts.py` → OK
- `uv run python scripts/agent_harness_probe.py --strict` → OK (14/14)

머지 후:

- PR #396 `pr-quality-gate` → success
- `Deploy on merge to main` run `28282838560` → success
- 열린 PR 조회 → `[]`

handoff 갱신 후:

- `uv run python scripts/check_handoff_facts.py` → OK
- `uv run python scripts/agent_harness_probe.py --strict` → OK (14/14)
- `uv run pytest -q` → 2286 passed, 4 skipped
- `uv run ruff check src tests` → All checks passed

## 다음 세션 한 줄

전략 검토 루프는 이제 모든 후보가 최소 관측 전인 정상 누적 차이를 장애로 보지 않는다. 다음
reassign 실행은 `globalfixed` 관측 지연을 참고 정보로 표시하되, 비교 가능한 도전자가 나올 때까지
재지정은 계속 HOLD해야 한다.
