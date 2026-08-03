# HANDOFF-127 — Live Canary Observe Gateway

## 상태

완료. #568과 #569가 live canary sidecar freshness와 내용 복구를 닫았다. post-merge 배포, live canary main run, pipeline-liveness, money-path, capital-path-readiness까지 새로 확인했다.

## 왜 했나

돈 경로 자체는 `PREVIEW_ONLY`/`NO_EDGE_YET`라 실주문을 막고 있었다. 그런데 `pipeline-liveness`가 critical sidecar인 `rebalance-live-canary`를 `LATE`로 보고했다.

첫 원인은 live canary workflow가 하나의 production approval job에 묶여 있었던 것이다. `armed=false`라 실제 주문이 절대 나가지 않는 미리보기 상태에서도 approval queue에 걸려 sidecar가 새로고침되지 않았다.

PR #568은 이 문제를 preview/status job과 production real-order job 분리로 고쳤다. 하지만 post-merge main run에서 sidecar 내용이 `refused command`로 비었다. 서버의 forced-command SSH gateway가 preview/backfill/measure raw remote shell 명령을 거부했기 때문이다.

## 무엇을 고쳤나

- #568은 `rebalance-live-canary.yml`을 preview/status job과 production real-order job으로 나눴다.
- preview/status job은 production approval 없이 sidecar를 새로고침한다.
- 실주문 명령 `--mode live --confirm-live`는 production-gated real-order job에만 남겼다.
- #569는 preview/status job의 raw `cd /opt/auto-invest && uv run ...` 원격 shell을 제거했다.
- #569는 fixed gateway 명령 `observe live-canary-backfill`, `observe live-canary-preview <capital>`, `observe live-canary-measure <capital>`을 추가했다.
- 서버 observe helper는 이 세 명령에서 backfill, dry-run preview, NAV snapshot, forward-verdict만 실행한다.
- observe helper에는 `--confirm-live`가 없다. 즉 새 gateway 명령은 주문 확정 경로가 아니라 관측/미리보기 경로다.
- gateway/helper refresh 직후 짧은 race를 견디도록 workflow에 `refused command` 재시도 루프를 넣었다.

## 확인한 증거

- PR #568 merge commit: `3076dd11e86113d044fb1f05ff582532e32ac2da`.
- PR #569 merge commit: `5a561172907206b51469b2591bbfe90b574af224`.
- #568 기능 커밋: `95f2cd6`.
- #569 기능 커밋: `791aef7`, follow-up task status commit `48842c6`.
- #569 Deploy on merge run `30777301767`: success.
- 배포 로그에서 `AUTO_INVEST_SSH_BOUNDARY_HELPERS_REFRESHED`와 `observe_helper=/usr/local/sbin/auto-invest-observe` 확인.
- Live canary main run `30777338028`: success. preview job success, real-order job skipped.
- 최신 `automation/rebalance-live-canary-last-run:LAST_RUN.md`: timestamp `2026-08-03T01:38:34Z`, `armed=false`, `preview-job-skipped`, `refused command` 없음.
- 최신 live canary sidecar 드라이런: `planned_buy_notional_usd=0.00`, `planned_sell_notional_usd=222.82`, `target_weights={"SPY":"0.235870"}`.
- 최신 live track 측정: NAV snapshot seq `16214`, `total_nav_usd=500.0`, forward verdict `INSUFFICIENT_DATA`, `n_obs=14 < min_obs_required=20`.
- Pipeline liveness run `30777384529`: success, overall `OK`, `rebalance-live-canary` `OK`, age 0.0h.
- Money-path run `30777446988`: success, `PREVIEW_ONLY`/`NO_EDGE_YET`, 관측 30회, 칼마 PASS, PSR `0.547840 < 0.95` FAIL.
- Capital-path-readiness run `30777476105`: success, `ACCUMULATING_EDGE`, 우선 후보 없음, pipeline-liveness input `overall=OK`.
- #569 로컬 검증: focused workflow/security/backfill/NAV tests 25 passed, SSH boundary/observe tests 16 passed, pipeline/readiness tests 42 passed, `bash -n` helper syntax 통과, workflow YAML parse `yaml-ok`, `uv run pytest` 2710 passed/5 skipped, `uv run ruff check src tests` 통과, `agent_harness_probe.py --strict` OK(14/14), `check_handoff_facts.py` OK, `git diff --check` 통과, PR quality gate 통과.

## 안전 경계

실제 주문, 실거래 전환, live 재무장, 자본 배분, whitelist/caps 확대, 손실 예산 변경, KIS secret, 감사 로그 삭제, 헌법, kernel manifest는 바꾸지 않았다.

새로 연 SSH gateway 명령은 live canary preview/status 전용이다. `--confirm-live`를 노출하지 않으며, 주문 라우터 호출도 dry-run preview만 한다. real-order job은 여전히 production approval 뒤에 있고, 현재 `armed=false`라 실행되지 않는다.

## 다음 세션 판단

live canary sidecar가 늦거나 `refused command`로 비는 병목은 닫혔다. 파이프라인 생존 감시는 다시 `OK`다.

돈 경로가 열린 것은 아니다. 최신 money-path는 `PREVIEW_ONLY`/`NO_EDGE_YET`이고 capital-path-readiness는 `ACCUMULATING_EDGE`다. 지금 실제 주문을 막는 직접 이유는 전진 성과의 엣지 신뢰도다. PSR은 `0.547840`으로 기준 `0.95`보다 낮다.

다음 세션은 먼저 최신 sidecar들을 fetch해서 `NO_EDGE_YET`가 바뀌었는지 확인한다. real-order job을 observe gateway로 옮기거나 `--confirm-live` gateway를 추가하는 일은 실제 주문 경계 변경이므로 운영자 명시 승인 없이 하지 않는다.
