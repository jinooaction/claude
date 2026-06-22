# HANDOFF 054 — 스펙 058 마이크로 GTAA 실거래 캐너리 (2026-06-22)

main 베이스라인: `f3d5085`(PR #374). 운영자가 실제 돈 투입 시점을 가능한 빠르게 앞당기되
세계 최고 수준과 최대 수익을 목표로 하라고 지시했고, 기존 증거 기반 자본 사다리를 낮추지 않는
별도 마이크로 실거래 캐너리를 출시했다.

## 무엇이 출시됐나

- `specs/058-micro-gtaa-canary/` SDD 산출물 전체.
- `deploy/micro-gtaa-live-portfolio.toml`: `SPYM`·`IEF`·`GLDM` 동일가중 GTAA, 정규장 지정가,
  일일 손실 3%, 총 낙폭 5%.
- `automation/rebalance-micro-gtaa.request`: 기본 `armed:false`, `capital_usd:1000`.
- `.github/workflows/rebalance-micro-gtaa-canary.yml`: push는 미리보기 전용, 수동/스케줄 실행만
  실주문 가능. 실주문 전 `evaluate_from_audit` 손실 브레이커를 평가하고 위반 시 `data/halt.flag`를
  세운다.
- `tests/unit/test_micro_gtaa_canary.py`와 기존 포트폴리오 설정 테스트에 센티넬, 워크플로,
  브레이커 순서, 포트폴리오 불변식 회귀를 추가했다.

## 실주문 조건

실제 주문은 아래 조건이 모두 참일 때만 가능하다.

- `automation/rebalance-micro-gtaa.request`의 `armed:true`.
- `capital_usd`가 1 이상 1,000 이하.
- 이벤트가 `push`가 아님. 머지/무장 push는 계속 미리보기만 한다.
- 사전 손실 브레이커가 통과.
- 기존 `rebalance-once --mode live --confirm-live`, `OrderRouter`, K1 캡, whitelist, `LIMIT`,
  `REGULAR`, halt gate가 모두 통과.

## 머지 후 확인

- PR #374 머지 커밋: `f3d5085`.
- `Deploy on merge to main` run `27934619924`: success. 이 배포는 dry-run 워커 코드 반영이며
  실거래 전환이 아니다.
- `Micro GTAA live canary rebalance (guarded, real money)` run `27934619940`: success.
- sidecar `automation/rebalance-micro-gtaa-last-run`: `armed=false`, `event=push`,
  `LIVE 스텝=skipped`, "드라이런 미리보기만 — 실주문 0건."
- KIS smoke sidecar 최신: run `27898040482`, `key_valid=true`, `smoke_state=success`.

## 검증

- PR #374 머지 전:
  - `uv run pytest` → 2222 passed, 4 skipped
  - `uv run ruff check src tests` → All checks passed
  - `uv run pytest tests/unit/test_micro_gtaa_canary.py tests/unit/test_canary_portfolio_config.py`
    → 13 passed
  - `uv run python scripts/agent_harness_probe.py --strict` → `OK (14/14)`
  - `uv run python scripts/check_handoff_facts.py` → `OK`
  - workflow YAML parse와 pre-live run block `bash -n` 통과
- 머지 직전 재검증:
  - `uv run pytest` → 2222 passed, 4 skipped
  - `uv run ruff check src tests` → All checks passed
- handoff 갱신 전:
  - `uv run pytest -q`는 stale `HANDOFF.md` 때문에 하네스 2건 실패. 이 handoff PR이
    `마지막 main 커밋` 행을 `f3d5085`로 고쳐 원인을 제거한다.

## 안전 경계

- 위험 등급: 4(돈 경로 변경)
- Kernel 터치: 없음
- 헌법 변경: 없음
- 비밀값 추가: 없음
- 기존 자본 사다리와 기존 라이브 캐너리 경로: 변경 없음
- 기본 상태: 실주문 0건
- 되돌림: `armed:false` 유지 또는 `data/halt.flag` 설정으로 신규 실주문 차단

## 다음 세션 한 줄

마이크로 GTAA는 이미 배포됐지만 기본은 비무장이다. 실거래를 원하면 sidecar 미리보기를 먼저 읽고
`armed:true`로 바꾼 뒤, push가 아닌 수동/스케줄 실행에서만 사전 손실 브레이커와 주문 게이트를
통과해야 한다.
