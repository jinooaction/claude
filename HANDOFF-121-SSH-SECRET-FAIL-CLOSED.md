# HANDOFF-121 — SSH secret fail-closed와 production 환경 완료

## 한 줄 결론

live-money workflow는 GitHub `production` 보호 환경 뒤로 들어갔고, SSH를 쓰는 일반 workflow는 deploy user·private key·known_hosts가 없으면 첫 SSH 호출 전에 명확히 실패하게 바뀌었다.

## 기준 상태

- 기준 `main`: `e5f8292fdeaaa06c21547eae94d17ee974b5b82a` — PR #534 SSH secret fail-closed 보강
- 직전 보안 머지: `2fe873e9177d1473df3d50be3d316268df88ae23` — PR #533 live-money workflow `production` 보호 환경 적용
- 기능 커밋: `759a1141ff9da83fdb5c38462e1695e6b3b3e34c`
- 돈 경로: `PREVIEW_ONLY`, `can_submit_real_orders=false`
- 실제 주문·취소·실거래 전환·자본 배분: 수행하지 않음

## 무엇을 닫았나

- GitHub `production` environment를 만들고, `main` branch만 허용하며 `jinooaction` required reviewer를 요구하게 설정했다.
- `go-live-canary`, `rebalance-live-canary`, `rebalance-micro-gtaa-canary`, `release-halt` job이 `environment: production`을 선언한다.
- 20개 SSH workflow의 `Install SSH key` 단계를 공통 `scripts/ci_secure_ssh.sh` 호출로 통합했다.
- 공통 helper는 `VULTR_SSH_USER` 또는 `SSH_USER`가 없으면 `missing VULTR_SSH_USER/SSH_USER`로 exit 2 한다.
- 공통 helper는 `VULTR_SSH_PRIVATE_KEY` 또는 `KEY`가 없으면 `missing VULTR_SSH_PRIVATE_KEY/KEY`로 exit 2 한다.
- 공통 helper는 `VULTR_SSH_KNOWN_HOSTS` 또는 `KNOWN_HOSTS`가 없으면 `missing VULTR_SSH_KNOWN_HOSTS/KNOWN_HOSTS`로 exit 2 한다.
- 공통 helper는 `root` deploy user를 계속 거부한다.
- `verify-operator-setup.yml`은 키 줄바꿈 복구 자체를 검증하는 특수 진단 경로라 ad-hoc 검증을 유지했다.

## 검증

- #533 브랜치 검증: `uv run pytest` → 2680 passed, 5 skipped.
- #533 브랜치 린트: `uv run ruff check src tests` → All checks passed.
- #534 브랜치 focused SSH/workflow 회귀: 28 passed.
- #534 브랜치 전체 테스트: `uv run pytest` → 2682 passed, 5 skipped.
- #534 브랜치 린트: `uv run ruff check src tests` → All checks passed.
- #534 브랜치 형식 검증: `git diff --check`, `bash -n scripts/ci_secure_ssh.sh` 통과.
- 하네스: `uv run python scripts/agent_harness_probe.py --strict` → OK (14/14).
- HANDOFF 사실 검증: `uv run python scripts/check_handoff_facts.py` → OK.
- PR 품질 관문: PR #533, PR #534 모두 통과.

## post-merge 자동화

- PR #534 merged at 2026-07-21T15:54:04Z, merge commit `e5f8292fdeaaa06c21547eae94d17ee974b5b82a`.
- `Deploy on merge to main` run `29846134323`: failure. `Install SSH key` 단계가 `missing VULTR_SSH_USER/SSH_USER`로 실패했다.
- `Forward anchored verdict` run `29846134390`: failure. `Install SSH key` 단계가 `missing VULTR_SSH_USER/SSH_USER`로 실패했다.
- `Regime-stratified strategy performance` run `29846134311`: failure. `Install SSH key` 단계가 `missing VULTR_SSH_USER/SSH_USER`로 실패했다.
- `Released work ledger` run `29846134307`: success, `overall_status=OK`, `released_count=38`.
- `Money-path readiness` run `29846134317`: success, `PREVIEW_ONLY`, `can_submit_real_orders=false`.
- `KIS smoke (autonomous)` run `29846134420`: workflow success, sidecar `secrets_present=false`, `smoke_state=(unset)`.
- `Autonomous work execution loop` run `29846134298`: success, 현재 실행 가능한 안전 후보 없음.
- `Execution quality package` run `29846151715`: success, `overall_status=OBSERVE`, latest signal `INTENT_LOSS`.

## 안전 경계

- 위험 등급 3 안전 경계 변경이다.
- GitHub Actions에서 서버와 live-money 경계로 들어가는 길을 좁혔다.
- K1 주문 제한, K4 감사 로그, 헌법, kernel manifest는 바꾸지 않았다.
- 실거래 모드, 자본, 주문, KIS secret, whitelist/caps, 손실 예산은 바꾸지 않았다.
- GitHub root SSH secret은 되살리지 않았다.
- 새 secret 값을 읽거나 등록하지 않았다.

## 남은 현실

서버 실제 `repair-ssh-boundary.sh` 실행과 non-root deploy private key 등록은 아직 서버 접근 권한이 없어 직접 완료하지 못했다. 이 상태에서는 deploy, anchored verdict, regime-stratify의 원격 SSH 단계가 실패하는 것이 정상이다.

다음 서버 접근 가능 세션은 root 콘솔 또는 검증된 out-of-band root SSH에서 `deploy/repair-ssh-boundary.sh`를 실행한 뒤 GitHub에 non-root `VULTR_SSH_USER`와 `VULTR_SSH_PRIVATE_KEY`를 등록하고 수동 `Verify operator setup`을 돌리면 된다. 그 전까지 돈 경로는 `PREVIEW_ONLY`이고 실주문은 불가하다.
