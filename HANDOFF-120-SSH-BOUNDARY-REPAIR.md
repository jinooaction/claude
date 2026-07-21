# HANDOFF-120 — SSH boundary repair 후속 보강

## 한 줄 결론

스펙 119의 남은 서버 조치였던 root SSH key retire와 non-root forced-command deploy identity 설치를 repo 안의 검증 가능한 `deploy/repair-ssh-boundary.sh` 경로로 만들었고, 배포 워크플로는 gateway 고정 명령만 호출하게 바뀌었다.

## 기준 상태

- 기준 `main`: `82296aa86aa45be6050770a73ea19fccd61452b8` — PR #531 SSH boundary repair 후속 보강
- 기능 커밋: `19052de48dc380937fcc9301ade7d86c5c554f1e`
- GitHub Secrets: `VULTR_SSH_PRIVATE_KEY`와 `VULTR_SSH_USER`는 여전히 없음. `VULTR_SSH_KNOWN_HOSTS`는 있음.
- 돈 경로: `PREVIEW_ONLY`, `can_submit_real_orders=false`
- 실제 주문·취소·실거래 전환·자본 배분: 수행하지 않음

## 무엇을 닫았나

- `deploy/repair-ssh-boundary.sh`를 추가했다. 이 스크립트는 root로 실행될 때 fresh `DEPLOY_PUBLIC_KEY`만 받고 private-key material을 거부한다.
- 기본 deploy 사용자는 `gh-deploy`이고, `authorized_keys`에는 `restrict`, no-pty, no-agent-forwarding, no-port-forwarding, forced command가 들어간다.
- gateway는 `status`, `sync-units`, `start-deploy`, `deploy-journal`만 허용하고 그 외 명령은 exit 126으로 거부한다.
- sudoers는 `visudo -cf`로 검증한 뒤 설치하며, 허용 범위는 root-owned sync helper, deploy service start, deploy journal 조회로 좁혔다.
- root의 legacy `github-actions@auto-invest` key entry와 `/root/.ssh/auto_invest_gh` 파일만 targeted retire한다. unrelated root key를 통째로 지우지 않는다.
- `deploy-on-merge.yml`은 원격 `sudo bash -s`와 one-off untracked quarantine shell을 제거하고 gateway 명령만 호출한다.
- `verify-operator-setup.yml`은 원격 임의 상태 조회 shell 대신 gateway `status`만 호출한다.

## 검증

- PR #531 로컬 검증: `uv run pytest -q` → 2679 passed, 5 skipped.
- PR #531 로컬 린트: `uv run ruff check src tests scripts` → All checks passed.
- 형식 검증: `bash -n deploy/repair-ssh-boundary.sh scripts/operator_one_time_setup.sh deploy/sync-units.sh`, workflow YAML parse, `git diff --check` 통과.
- 좁은 보안 회귀: `uv run pytest tests/unit/test_ssh_boundary_repair.py tests/unit/test_sync_units.py tests/unit/test_security_workflow_hardening.py -q` → 36 passed.
- 하네스: `uv run python scripts/agent_harness_probe.py --strict` → OK (14/14).
- HANDOFF 사실 검증: PR 전 OK. #531 merge 뒤에는 이 handoff 갱신 전까지 stale이었다.

## post-merge 자동화

- PR #531 merged at 2026-07-21T02:01:39Z, merge commit `82296aa86aa45be6050770a73ea19fccd61452b8`.
- `Deploy on merge to main` run `29794726091`: failure. `VULTR_SSH_PRIVATE_KEY`와 `VULTR_SSH_USER`가 없으므로 gateway에 접근하지 못해 실패한 안전 중단이다.
- `Verify operator setup` run `29794726171`: success. push 이벤트에서는 missing secrets를 non-blocking diagnostic으로 기록하고 수동 검증은 실패 처리하는 기존 계약을 유지했다.
- `Released work ledger` run `29794726161`: success, `overall_status=OK`, `released_count=38`.
- `Autonomous work execution loop` run `29794726117`: success, 실행 가능한 안전 후보 없음.
- KIS smoke sidecar는 아직 commit `6a46735` 기준이며 `secrets_present=false`, `smoke_state=(unset)`이다. #531은 KIS smoke workflow를 직접 트리거하지 않았다.

## 안전 경계

- 위험 등급 3 안전 경계 변경이다. 서버 deploy SSH 경계와 배포 워크플로의 원격 실행 방식을 좁혔다.
- K1 주문 제한, K4 감사 로그, 헌법, kernel manifest는 이번 후속 PR에서 바꾸지 않았다.
- 실거래 모드, 자본, 주문, KIS secret, whitelist/caps, 손실 예산은 바꾸지 않았다.
- GitHub root SSH secret은 되살리지 않았다.

## 남은 현실

이 세션은 로컬 SSH `root`, `auto-invest`, `gh-deploy` 모두 `Permission denied`였고, GitHub/Vultr API secret도 없었다. 따라서 실제 서버의 `/root/.ssh/authorized_keys`를 직접 수정하거나 `repair-ssh-boundary.sh`를 서버에서 실행하지는 못했다.

다음 서버 접근이 가능한 세션은 root 콘솔 또는 검증된 out-of-band root SSH에서 `deploy/repair-ssh-boundary.sh`를 실행한 뒤, GitHub에 non-root `VULTR_SSH_USER`/`VULTR_SSH_PRIVATE_KEY`를 새로 등록하고 수동 `Verify operator setup`을 돌리면 된다. 그 전까지 deploy failure는 정상 안전 중단이다.
