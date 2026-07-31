# HANDOFF-123 — Promote Readiness Observe Gateway

## 상태

완료. #559와 #560이 함께 스펙 121을 닫았다.

## 왜 했나

`promote-readiness` sidecar가 `ssh_exit=126`으로 막혀 헌법 VI(라이브 트랙레코드) 승격 준비도가 보이지 않았다. 처음 원인은 workflow가 raw SSH command를 보내는 것이었고, #559 뒤에는 서버에 설치된 root-owned gateway/helper가 낡아 있는 설치본 drift가 남았다.

## 무엇을 고쳤나

- #559: `promote-readiness.yml`이 raw `uv run auto-invest promote-check` 대신 fixed `observe promote-readiness`를 사용하게 했다.
- #559: forced-command gateway와 observe helper에 argument 없는 report-only `promote-readiness` 경로를 추가했다.
- #560: `auto-invest-deploy.service`가 deploy 전 root-only pre-step으로 `origin/main`의 gateway/helper/sudoers를 갱신하게 했다.
- #560: `refresh-ssh-boundary-helpers.sh`와 `REFRESH_HELPERS_ONLY=1` repair mode를 추가했다.

## 확인한 증거

- PR #560 merge commit: `85584eddcf2efb7ab246350ca1b7f97d4bc36ee3`.
- Deploy on merge run `30592573381`: success. 로그에 `AUTO_INVEST_SSH_BOUNDARY_HELPERS_REFRESHED`, gateway path, observe helper path가 남았다.
- 수동 Promote readiness run `30592627513`: success. 최신 sidecar는 commit `85584ed`, `ssh_exit=1`, READY=false, stderr empty다. 즉 서버 거부 126은 해소됐고, 평가가 정상 실행된 뒤 not-ready를 보고한다.
- #560 브랜치 검증: focused test 32 passed, `uv run pytest` 2703 passed/5 skipped, `uv run ruff check src tests` 통과, `check_handoff_facts.py` OK, `agent_harness_probe.py --strict` OK(14/14), `git diff --check` 통과, PR quality gate 통과.

## 안전 경계

실제 주문, live 재무장, 자본 배분, whitelist/caps 확대, 손실 예산 변경, KIS secret, 감사 로그, 헌법, kernel manifest는 바꾸지 않았다. 새 경로는 fixed observation command와 root-owned helper refresh만 다룬다.

## 다음 세션 판단

서버/KIS 관측 setup 차단은 이번 건에서는 닫혔다. 최신 money-path는 여전히 `PREVIEW_ONLY`/`NO_EDGE_YET`이고, 최신 promote-readiness는 READY=false다. 다음 실행 가능한 후보가 없으면 autonomous-work의 `wait-for-fresh-evidence` 상태를 그대로 받아들이고, 새 scheduled sidecar 후 released-work/autonomous-work를 다시 읽는다.
