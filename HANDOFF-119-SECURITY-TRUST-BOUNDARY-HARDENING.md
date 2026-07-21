# HANDOFF-119 — 보안 신뢰 경계 강화

## 한 줄 결론

GitHub Actions가 서버 root SSH 키로 곧장 운영 서버와 실거래 경로에 닿던 구조를 main에서 차단했고, GitHub에 있던 root SSH user/private-key secrets도 제거했다.

## 기준 상태

- 기준 `main`: `6a4673527a9947d29f2a594808c5f036f0a3b2ec` — PR #529 보안 신뢰 경계 강화
- 기능 커밋: `5e90f3ce7d54c61f81a494a0dc5ed80d268e3950`
- 후속 보정 커밋: `0d91c4ba10c5926704f196d106fec949abea5173`, `b77885fa497d5112863b064a793fc86edc64a501`, `46d5982dcda240b863b727aaea5bff3b9d6c29ae`
- 확인 시점: 2026-07-21 KST
- 돈 경로: 계속 `PREVIEW_ONLY`
- 실제 주문·취소·실거래 전환·자본 배분: 수행하지 않음
- GitHub Secrets: `VULTR_SSH_PRIVATE_KEY`와 `VULTR_SSH_USER` 삭제 완료, `VULTR_SSH_KNOWN_HOSTS` 등록 완료

## 무엇을 닫았나

ChatGPT 보안 리뷰가 지적한 핵심 위험은 저장소·Actions 권한이 서버 root 권한과 실거래 주문 경로까지 이어지는 신뢰 경계 붕괴였다. #529는 그 경로를 다음처럼 fail-closed로 바꿨다.

- GitHub SSH 워크플로는 고정 `known_hosts` 없이는 진행하지 않고, `VULTR_SSH_USER=root`를 거부한다.
- `capital` 같은 원격 입력은 숫자 스키마를 먼저 통과해야 하며 셸 메타문자를 거부한다.
- `.env`는 셸 코드로 `source`하지 않고 허용 목록 파서로 데이터처럼 읽는다.
- `go-live-canary.sh`는 `set -euo pipefail`, expected SHA 일치, 시장 상태 `CLOSED` 전용 진행, 원자 `.env` 교체, 전체 rollback을 사용한다.
- canary 승인은 code SHA와 ruleset SHA가 모두 정확히 일치하는 `CANARY_PASSED` 감사 기록만 인정한다.
- 배포 락은 프로세스 수명과 묶인 `fcntl.flock`으로 바꿨다.
- broker token cache는 symlink 거부, 0700/0600 권한, 임시 파일 fsync, 원자 replace를 사용한다.
- 주문 라우터는 `SUBMITTING` 상태를 기록하고 stale `INTENT/SUBMITTING` BUY를 신규 BUY 차단 조건에 포함한다.
- unknown submission 복구는 시간, 거래소, 주문 유형, 가격까지 맞는 강한 매칭일 때만 자동 연결한다.
- risk gate는 신규 노출 증가와 검증된 reduce-only 청산을 구분하고 oversell은 거부한다.
- 공개 sidecar 발행 전 디렉터리 전체 redaction을 적용한다.

## post-merge 자동화

- PR #529: merged at 2026-07-20T23:55:50Z, merge commit `6a4673527a9947d29f2a594808c5f036f0a3b2ec`.
- `Deploy on merge to main` run `29788767866`: failure. 원인은 root SSH user/private-key secrets 제거 후 SSH exit 255로 원격 배포 재료가 없어진 상태다. 이는 이번 보안 조치의 의도된 안전 중단이며, worker는 직전 good SHA를 유지한다.
- `Verify operator setup` run `29788767789`: success. push 이벤트에서는 셋업 실패를 경고/summary로만 남기고, 수동 `workflow_dispatch` 검증은 실패로 처리한다.
- `KIS smoke (autonomous)` run `29788767839`: workflow success이지만 sidecar 기준 `secrets_present=false`, `smoke_state=(unset)`이다. 즉 브로커 read-only smoke까지 들어가지 않았다.
- 그 외 main push 워크플로는 `gh run list --commit 6a46735` 기준 성공이다. `Collect public data`, `Money-path readiness`, `Execution quality package`, `Released work ledger`, `Autonomous work execution loop`, `Pipeline liveness`가 모두 완료됐다.

## 검증

- PR 브랜치 최종 HEAD 기준 `uv run pytest -q` → 2669 passed, 5 skipped.
- PR 브랜치 최종 HEAD 기준 `uv run ruff check src tests scripts` → All checks passed.
- `git diff --check origin/main..HEAD`와 `git diff --check` → 통과.
- shell 문법: 변경된 shell scripts `bash -n` → 통과.
- `.github/workflows/*.yml` YAML parse → `yaml ok`.
- 등급 3 하네스: `uv run python scripts/agent_harness_probe.py --strict` → OK (14/14).
- HANDOFF 사실성: PR 전 `uv run python scripts/check_handoff_facts.py` → OK. #529 merge 뒤에는 `HANDOFF.md`가 stale이 되어 전체 테스트에서 하네스 관련 2개가 실패했고, 이 handoff 갱신이 그 상태를 바로잡는다.
- PR #529 체크: `pr-quality-gate` success, `verify` success, `mergeable=MERGEABLE`, `mergeStateStatus=CLEAN`.

## 안전 경계

- 위험 등급 3 안전 경계 변경이다.
- K1 포지션 한도/주문 제한 경계: `src/auto_invest/risk/gates.py`에서 reduce-only/oversell 판단을 추가했다.
- K4 감사 로그 경계: `src/auto_invest/persistence/audit.py`와 canary 흐름에서 ruleset hash 증거를 추가했다.
- 실제 주문, 주문 취소, 실거래 재무장, 자본 증액, 자본 배분, whitelist/caps 확대, 손실 예산, 헌법, kernel manifest는 바꾸지 않았다.
- GitHub root SSH private key는 저장소 secret에서 제거했지만, 서버의 `/root/.ssh/authorized_keys`에 남은 공개키 제거 여부는 이 세션에서 확인하지 못했다.

## 다음 세션이 알아야 할 것

지금 main은 “GitHub에서 서버 root로 배포/실거래 경로에 들어가는 길”을 끊은 상태다. 따라서 원격 배포와 KIS smoke는 새 제한 deploy 사용자와 fresh `VULTR_SSH_USER`/`VULTR_SSH_PRIVATE_KEY`가 생기기 전까지 정상 진입하지 않는다. 다음 운영 작업의 첫 번째 후보는 서버 콘솔이나 검증된 out-of-band SSH로 기존 root 공개키를 제거하고, 제한 deploy 사용자와 고정 명령 gateway를 설치한 뒤 GitHub secrets를 새 non-root 키로 다시 채우는 것이다.
