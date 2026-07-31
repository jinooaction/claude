# HANDOFF-124 — Forward Paper DB Writability

## 상태

완료. #562가 스펙 122를 닫았고, post-merge forward paper 재관측까지 성공했다.

## 왜 했나

돈 경로는 `PREVIEW_ONLY`/`NO_EDGE_YET`라 실주문을 막고 있었다. 그런데 최신 forward paper sidecar도 모든 prep step에서 `OperationalError: attempt to write a readonly database`를 남겨, 엣지 판정에 필요한 새 관측을 쌓지 못하고 있었다.

## 무엇을 고쳤나

- `observe paper-track-run` 시작 전에 `ensure_paper_track_storage`가 종이거래 전용 DB/WAL/SHM과 트랙별 halt flag만 쓰기 가능하게 복구한다.
- 복구 대상은 `data/forward_*.db`, `data/forward_*.db-wal`, `data/forward_*.db-shm`, `data/forward_*.halt.flag`로 제한했다.
- `data/auto_invest.db`, `data/halt.flag`, 비밀값, live 설정, 자본, 주문 경로는 건드리지 않는다.
- 예상 밖 경로나 symlink는 권한 변경 전에 실패한다.

## 확인한 증거

- PR #562 merge commit: `1643410b88a422402dccb4ba7e3742d54cc61e86`.
- Deploy on merge run `30596929563`: success. 로그에서 `origin/main:deploy/observe-on-instance.sh`와 `observe_helper=/usr/local/sbin/auto-invest-observe` 갱신을 확인했다.
- Rebalance forward paper run `30596973332`: success. 최신 sidecar timestamp `2026-07-31T01:44:16Z`, 7개 트랙 prep/verdict 모두 `ssh_exit=0`.
- 최신 forward sidecar에는 `OperationalError`와 `attempt to write a readonly database` 문자열이 없다.
- 최신 edge-autoarm run `30597184383`: `WAIT_EDGE`, forward verdict `NO_EDGE`, sentinel 변경 없음, PR 없음.
- 최신 money-path run `30597231376`: `PREVIEW_ONLY`/`NO_EDGE_YET`, forward 관측 28회, PSR `0.400049 < 0.95`.
- 최신 capital-path-readiness run `30597231465`: `ACCUMULATING_EDGE`, 우선 후보 없음.
- 최신 autonomous-work run `30597261537`: selected_work=`wait-for-fresh-evidence`, status=`OBSERVATION_WAIT`.
- #562 브랜치 검증: focused tests 17 passed, `uv run pytest` 2705 passed/5 skipped, `uv run ruff check src tests` 통과, `check_handoff_facts.py` OK, `agent_harness_probe.py --strict` OK(14/14), `git diff --cached --check` 통과, PR quality gate 통과.

## 안전 경계

실제 주문, live 재무장, 자본 배분, whitelist/caps 확대, 손실 예산 변경, KIS secret, 감사 로그, 헌법, kernel manifest는 바꾸지 않았다. 이 변경은 종이거래 관측 저장소만 복구한다.

## 다음 세션 판단

서버 권한 drift로 forward paper 증거가 멈추던 병목은 닫혔다. 하지만 돈 경로가 열린 것은 아니다. 최신 상태는 `PREVIEW_ONLY`/`NO_EDGE_YET`이고, 자율 루프는 새 증거를 기다린다. 다음 세션은 먼저 최신 `money-path`, `edge-autoarm`, `rebalance-paper-forward`, `autonomous-work` sidecar를 fetch해서 `NO_EDGE`가 바뀌었는지 확인한다.
