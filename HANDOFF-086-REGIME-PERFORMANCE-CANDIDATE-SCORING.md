# HANDOFF 086 — 레짐·성과 후보 점수화 (2026-07-02 KST)

main 코드 베이스라인: `0a5ad0f`(PR #446). 스펙 082는 자율 작업 실행 루프가 고른 `candidate-e481b0309206`를 처리한 등급 2 운영 보정이다. 레짐 층화와 승격 준비 성과 표면이 대화나 참고 문구에 머물지 않고 자율 성장 후보 점수의 증거 입력으로 들어가게 했다.

## 무엇이 바뀌었나

- `src/auto_invest/analytics/evolution_loop.py`
  - evidence manifest에 `promote-readiness`를 추가했다.
  - 분석 후보 생성 로직을 `_analysis_candidate`로 분리했다.
  - `candidate-e481b0309206` evidence refs가 `regime-stratify`, `public-data`, `promote-readiness`를 함께 기록한다.
  - 정상 `READY=false`는 성과 보고로 쓰고, 누락·stale·셋업 오류는 `sidecar_freshness` 의존으로 낮춘다.
- `tests/fixtures/evolution_loop/`
  - fresh/stale `promote-readiness` fixture를 추가했다.
- `tests/unit/test_evolution_loop.py`
  - fresh, missing, stale, setup-error-like `promote-readiness`가 점수와 증거 의존성에 미치는 영향을 고정했다.
- `tests/integration/test_evolution_loop_probe.py`
  - manifest가 `promote-readiness	automation/promote-readiness-last-run	LAST_RUN.md`를 포함하는지 확인한다.
- `specs/082-regime-performance-candidate-scoring/`
  - SDD 산출물과 quickstart, 계약, tasks를 남겼다.
  - 이 handoff에서 T017을 닫고 `completed_candidate_id: candidate-e481b0309206` 마커를 추가했다. 다음 released-work 실행은 이 후보를 완료 처리해야 한다.

## 운영상 의미

- 자율 성장 루프는 이제 `promote-readiness`를 매번 수집한다.
- `READY=true`와 `READY=false`는 둘 다 승격 실행 신호가 아니다. 후보 점수의 읽기 전용 성과 증거일 뿐이다.
- 성과 표면이 없거나 오래됐거나 셋업 오류이면 후보가 과신 상태로 남지 않고 증거 신선도 의존으로 내려간다.
- handoff checkout 기준 로컬 재현에서 `released-work`는 `candidate-e481b0309206`를 `released`로 소비하고, 다음 자율 작업 실행 후보는 `candidate-dff4f9344b02`(`주문 거부·체결 품질 손익 관측`)로 이동한다.

## 배포 후 실제 실행 증거

- PR #446 merge commit: `0a5ad0f95be67a863f6f0c3ab37aed4d1af5f968`
- `Deploy on merge to main` run `28566029103`: success, commit `0a5ad0f`
- `Autonomous evolution loop` run `28566029110`: success, commit `0a5ad0f`
- `Autonomous work execution loop` run `28566029113`: success, commit `0a5ad0f`
- `Released work ledger` run `28566029091`: success, commit `0a5ad0f`
- deploy job steps all success: checkout, SSH key install, stuck deploy quarantine, systemd unit sync, off-hours-guarded oneshot trigger, summary.
- 컨테이너에서 서버 `audit_log`는 직접 확인하지 못했다. 운영자 확인 표면은 GitHub Actions Summary와 서버 `DEPLOY_*` audit rows다.

최신 `origin/automation/autonomous-evolution-last-run:LAST_RUN.md`:

- `run_id=28566029110`
- `commit=0a5ad0f95be67a863f6f0c3ab37aed4d1af5f968`
- `overall_status=ok`
- `candidate-e481b0309206` 점수 560
- 안전 문구: 주문, 자본, whitelist, caps, live 전략 변경 없음

최신 `origin/automation/autonomous-evolution-last-run:candidate_backlog.json`에서 확인한 후보:

```json
{
  "candidate_id": "candidate-e481b0309206",
  "evidence_refs": [
    "regime-stratify",
    "public-data",
    "promote-readiness"
  ],
  "composite_score": 560,
  "evidence_dependency": "none",
  "status": "new"
}
```

handoff checkout에서 완료 마커까지 포함해 재현한 released-work 결과:

- `candidate-e481b0309206` — `082-regime-performance-candidate-scoring` — `released`
- `candidate-fd04772a23c5` — `078-money-gate-alignment-loop` — `released`
- `candidate-fd04772a23c5` — `079-completed-candidate-consumption` — `released`

handoff checkout에서 재현한 다음 자율 작업 후보:

- `candidate-dff4f9344b02` — 주문 거부·체결 품질 손익 관측
- `autonomy_level=CODEX_AUTONOMOUS_START`
- `risk_grade=2`

## 안전 경계

- 위험 등급: 2(운영 자동화 보정)
- 실제 주문 실행: 없음
- 브로커 실주문 API 호출: 없음
- 자본 증액, 자본 배분, 허용 종목 확대, 포지션 한도 완화, live 전략 교체, live sentinel 변경: 없음
- 헌법, 커널 목록, 주문 제한, 감사 로그 schema, 비밀값 저장, 외부 유료 서비스 변경: 없음
- 배포 성공은 dry-run worker 코드 반영이다. 실거래 전환이나 실제 주문을 의미하지 않는다.
- 최신 KIS smoke sidecar는 run `28523981341`, commit `996ce56`, `smoke_state=success`, `key_valid=true`다. #446 이후 실행은 아니므로 배포 증거가 아니라 최근 읽기 전용 브로커 생존 참고로만 본다.

## 검증

PR #446 머지 전:

- `uv run pytest tests/unit/test_evolution_loop.py tests/integration/test_evolution_loop_probe.py -q` -> 31 passed
- `uv run pytest` -> 2421 passed, 4 skipped
- `uv run ruff check src tests` -> All checks passed
- `git diff --check` -> OK
- `uv run python scripts/check_pr_quality_gate.py --template .github/pull_request_template.md` -> OK
- `uv run python scripts/check_pr_quality_gate.py /tmp/pr-082-body.md` -> OK
- `uv run python scripts/check_handoff_facts.py` -> OK
- `uv run python scripts/agent_harness_probe.py --strict` -> OK (14/14)
- latest sidecar local smoke: `candidate-e481b0309206` evidence refs에 `promote-readiness` 포함 확인
- PR 품질 관문 run `28566014468`: success

머지 후:

- deploy run `28566029103`: success
- autonomous evolution run `28566029110`: success
- autonomous work execution run `28566029113`: success
- released-work run `28566029091`: success
- latest evolution sidecar에서 `promote-readiness` 포함 확인
- handoff checkout local smoke에서 completed marker가 `released-work`와 다음 작업 선택에 반영되는 것 확인

## 다음 세션 한 줄

스펙 082는 완료됐다. 자율 성장 루프는 이제 레짐·성과 표면을 후보 점수 입력으로 쓰고, handoff merge 뒤 같은 후보는 `released-work`에 소비되어 다음 후보 `candidate-dff4f9344b02`로 넘어가야 한다.
