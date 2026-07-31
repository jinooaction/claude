# HANDOFF-125 — Regime Stratify Observe Gateway

## 상태

완료. #564가 `regime-stratify` 연구 관측을 서버의 고정 `observe` gateway 안으로 옮겼고, post-merge 배포와 sidecar 재관측까지 성공했다.

## 왜 했나

돈 경로는 `PREVIEW_ONLY`/`NO_EDGE_YET`라 실주문을 막고 있었다. 동시에 `regime-stratify` sidecar는 workflow 자체는 success처럼 보였지만 실제 내용은 `ssh_exit=126`, `refused command: cd /opt/auto-invest && rm -rf ... uv run ...`, 타임라인 prep exit 255였다. 그래서 전략이 어떤 거시 레짐에서 벌고 잃는지 보는 연구 증거가 멈춰 있었다.

## 무엇을 고쳤나

- `regime-stratify.yml`에서 raw `scp`와 임의 inline SSH 명령을 제거했다.
- workflow는 이제 `observe regime-stratify global`과 `observe regime-stratify wide`만 호출한다.
- 서버 observe helper는 `origin/automation/public-data:regime_timeline.csv`를 `/tmp/regime_timeline.csv`로 읽고, `/tmp/stratify_<track>` 작업공간에서 bars export, history ingest, portfolio backtest, regime-stratify를 순서대로 실행한다.
- SSH gateway allowlist는 `observe regime-stratify global|wide`만 허용한다. 다른 트랙명이나 임의 명령은 계속 거부된다.
- workflow에는 새 helper가 배포 직후 서버에 반영되는 동안 생길 수 있는 짧은 경합을 위해, `refused command: observe regime-stratify`에 한정한 재시도만 넣었다.

## 확인한 증거

- PR #564 merge commit: `5fb249cc82d7ae5cffcdb0435417a679aec0c229`.
- Deploy on merge run `30630190101`: success. 로그에서 `AUTO_INVEST_SSH_BOUNDARY_HELPERS_REFRESHED`, `observe_helper=/usr/local/sbin/auto-invest-observe`, worker stop/start, deploy correlation id `1cfa275ddd763bb0211ccc627ba45756`을 확인했다.
- Regime stratify run `30630190081`: success. 최신 sidecar timestamp `2026-07-31T12:20:10Z`, 타임라인 prep exit 0, GLOBAL-TREND `ssh_exit=0`, GLOBAL-TREND-WIDE `ssh_exit=0`.
- 최신 regime-stratify sidecar에는 두 트랙 모두 `--- stratified json ---`와 `"schema_version": "1.0"`이 있다.
- GLOBAL-TREND 전체: 752일, 총수익 42.97%, 최대낙폭 10.48%, 샤프 1.30. RISK_ON은 313일, 총수익 30.51%, 샤프 2.19다.
- GLOBAL-TREND-WIDE 전체: 752일, 총수익 22.54%, 최대낙폭 5.78%, 샤프 1.11. RISK_ON은 313일, 총수익 15.07%, 샤프 1.97다.
- #564 브랜치 검증: focused tests 20 passed, adjacent tests 56 passed, `bash -n` helper syntax 통과, `uv run pytest` 2706 passed/5 skipped, `uv run ruff check src tests` 통과, `agent_harness_probe.py --strict` OK(14/14), `check_handoff_facts.py` OK, `git diff --check` 통과, PR quality gate 통과.

## 안전 경계

실제 주문, live 재무장, 자본 배분, whitelist/caps 확대, 손실 예산 변경, KIS secret, 감사 로그, 헌법, kernel manifest는 바꾸지 않았다. 이 변경은 연구 관측 경로만 복구한다.

## 다음 세션 판단

`regime-stratify`가 서버 보안 gateway에 막히던 병목은 닫혔다. 하지만 돈 경로가 열린 것은 아니다. 최신 money-path는 `PREVIEW_ONLY`/`NO_EDGE_YET`, edge-autoarm은 `WAIT_EDGE`, capital-path-readiness는 `ACCUMULATING_EDGE`, autonomous-work는 `wait-for-fresh-evidence`/`OBSERVATION_WAIT`다. 다음 세션은 먼저 최신 sidecar를 fetch해서 `NO_EDGE`가 바뀌었는지 확인한다.
