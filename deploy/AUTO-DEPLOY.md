# 자동 배포 파이프라인 — 머지 → main → 서버 (각 단계 자동 반영)

이 문서는 "각 단계(스펙/기능)가 완성되면 서버에 자동 배포된다"는 운영자 요구를
**정확히 어떤 장치가 어떤 순서로 보장하는지** 적은 단일 진실이다. 새 배포 로직을
만들지 않는다 — spec 006 의 `auto-invest deploy` 안전 기계를 **언제** 돌릴지를
정의할 뿐이다.

## 한눈에 보는 흐름

```
PR 머지 (feature → main)
        │
        ├─(A) 즉시: GitHub Actions `deploy-on-merge.yml`  ← 이번에 추가
        │        push:main → SSH → `systemctl start auto-invest-deploy.service`
        │
        └─(B) 늦어도 30분 내: 인스턴스 `auto-invest-deploy.timer`  ← 이미 설치됨
                 30분마다(미국 장중 제외) 같은 서비스를 자동 실행

        └─(E) 오너 긴급: GitHub 수동 실행의 단회 승인
                 정확한 current main 한 커밋만 주문 정지 뒤 장중 배포

둘 다 같은 한 가지를 실행한다:
        `uv run auto-invest deploy --branch main`   (auto-invest-deploy.service)
        │
        ▼
spec 006 배포 상태기계 (안전 단계 전부 통과해야 워커 교체)
  preconditions(락) → 변경없음 검사(noop) → 장중 통제(market_hours_guard,
  헌법 VIII.A: 일반 거부, 단회 오너 요청만 검증) → dirty tree → 시크릿 →
  git pull(origin/main) → kernel 확인 →
  [캐너리 게이트는 auto-tuner 트리거만] → sync → migrate → dry_run 검증 →
  worker restart → health_check(≥90초) → 실패 시 직전 good SHA 로 자동 롤백
```

(A)는 **즉시성**(머지 직후 몇 분 내 반영), (B)는 **안전망**(A가 실패하거나 머지가
장중에 일어났을 때 장 마감 후 자동 재시도)을 담당한다. 둘은 동일한 oneshot 서비스를
호출하므로 **안전 속성이 완전히 같다**. 일반 경로는 장중에 배포되지 않는다. 오너
긴급 경로(E)도 같은 상태기계를 사용하며, 추가로 자동 주문을 먼저 멈추고 미체결
주문 0건을 확인한다. 어느 경로든 건강 검사가 실패하면 직전 정상 버전으로 롤백한다.

## 왜 이게 안전한가 (운영자 자율 수행 + 돈 안전 분리)

1. **배포 ≠ 주문 승인.** 배포는 코드를 교체하고 워커를 재시작할 뿐, 실주문 이벤트·
   전략·자본·승격 단계를 바꾸지 않는다. 실거래는 기존 자동 예약과 모든 주문 관문을
   별도로 통과해야 한다.
2. **일반 장중 배포는 계속 금지.** 타이머 달력과 `market_hours_guard`(헌법 VIII.A)가
   DST 경계까지 막는다. 머지가 장중에 일어나면 (A)는 "장중 연기"로 끝나고 (B)가
   장 마감 후 올린다. 유일한 예외는 아래 (E)의 저장소 오너 단회 요청이다.
3. **실패하면 직전 good 코드로 자동 롤백.** health_check(≥90초) 통과 못 하면
   `DEPLOY_ROLLED_BACK` 후 이전 SHA 로 워커를 되돌린다. 깨진 배포가 워커를 죽인
   채 방치되지 않는다.
4. **Kernel 터치는 머지 단계에서 이미 감사된다.** main 에 들어온 코드만 배포되고,
   Kernel 터치 커밋 해시는 PR 본문/`git log` 로 추적된다(헌법 IX.A 포렌식 목록).
   배포 자체는 새 안전 경계를 만들지 않는다.

## (A) 머지 즉시 배포 — `.github/workflows/deploy-on-merge.yml`

- **트리거**: `push: branches: [main]` (PR 머지가 곧 main push). 순수 문서/스펙
  변경(`**.md`, `specs/**`, `.verify/**`, `.trigger/**`)은 `paths-ignore` 로 제외 —
  코드가 안 바뀌면 워커를 흔들지 않는다. 수동 재실행용 `workflow_dispatch` 포함.
- **동작**: 기존 `VULTR_SSH_*` 시크릿으로 인스턴스에 SSH →
  `sudo systemctl start auto-invest-deploy.service` (oneshot 이라 완료까지 블록,
  배포 결과 코드를 그대로 받음) → `journalctl` 마지막 120줄을 GitHub Actions
  Summary 에 기록. main 에 커밋을 만들지 않는다(재트리거 루프 방지).
- **장중 연기 처리**: 배포가 `market_hours_guard` 로 거부되면(journal 에 "market
  is open") 워크플로우는 **실패가 아니라 "장중 연기"** 로 표시하고 종료 0. 타이머(B)가
  장 마감 후 같은 배포를 올린다.
- **systemd 유닛 자동 동기화**: 배포 트리거 직후 `deploy/sync-units.sh` 를 서버
  `sudo bash` 에 파이프해 `deploy/` 의 유닛(.service/.timer)을 `/etc/systemd/system`
  에 설치하고 타이머를 활성화한다. 배포 상태기계는 코드만 나르고 **새 유닛 설치는
  안 하므로** 그 빈틈을 메운다(새 타이머를 추가했을 때 운영자가 서버에 손대지 않아도
  다음 머지에 자동 반영). 이 단계는 **워커를 재시작하지 않고**(주문 라우팅 무관)
  `git show origin/main:<path>` 로 작업트리도 안 건드리므로 장중에도 안전 — 배포가
  "장중 연기"여도 유닛/타이머는 이번 실행에서 갱신된다. 코드 배포와 독립이라 유닛
  동기화가 실패해도(예: 서버 sudo 범위 제한) 배포 결과를 가리지 않고 Summary 에 별도
  표시된다.
- **forced-command helper 자동 갱신**: `auto-invest-deploy.service`는 배포 상태기계 실행
  직전에 root 전용 `ExecStartPre=+...`로 `origin/main`의
  `deploy/refresh-ssh-boundary-helpers.sh`를 읽어 실행한다. 이 pre-step은 기존 deploy
  사용자와 키를 바꾸지 않고, root-owned gateway/helper 파일과 sudoers만 main 기준으로
  새로 설치한다. GitHub runner가 임의 셸을 보내는 것이 아니라, main에 머지된 고정
  helper만 서버가 가져와 적용하는 방식이다.

## (E) 오너 단회 장중 긴급 배포 — 헌법 VIII.A

이 경로는 일반 수동 배포가 아니다. GitHub의 `Deploy on merge to main`을 저장소
오너가 직접 실행하면서 다음 네 값을 모두 제출할 때만 열린다.

- `owner_emergency=true`
- `expected_sha`: 실행 시점의 정확한 40자리 `main` SHA
- `confirmation`: `OWNER_EMERGENCY_LIVE_DEPLOY`
- `reason`: 12~500자의 사유. 서버 감사에는 원문 대신 SHA-256 요약만 남는다.

승인은 10분 뒤 만료되고 최대 허용 수명은 15분이며 한 번만 소비된다. 일반
`start-deploy`가 장중 차단됐거나 이미 정상 완료된 뒤에도 고정 SSH 명령
`emergency-deploy`를 호출한다. 서버의 root helper가 current main과 stale 잠금 유무를
직접 판정하므로, 정상 배포가 끝나고 stale 상태도 없으면 아무 변경 없이 종료한다. 실제
긴급 배포가 필요한 경우 root helper는 current main을 다시 확인하고
`DEPLOY_EMERGENCY_AUTHORIZED` 감사를 먼저 남기고
`/run/auto-invest-deploy/live-order-maintenance.lock`을 만든다. 모든 실제 KIS 쓰기는
`/run/auto-invest-deploy/broker-write.lock`의 공유 잠금을 잡고, 긴급 배포는 같은 파일의
배타 잠금을 잡으므로 마지막 파일 확인과 네트워크 요청 사이의 경쟁도 닫힌다. 이어 두
자동 예약과 최종 KIS 주문 쓰기를 막는다. 새 잠금 코드를 아직 모르는 이전 버전까지
안전하게 다루기 위해 기존 scheduler timer·service·worker를 중지하고 비활성 상태를
확인한다. 그 뒤 KIS 미체결 주문이 0건임을 읽기 전용으로 확인한 다음에만 요청 파일을
배포 상태기계에 전달한다.

감사 순서는 `DEPLOY_EMERGENCY_AUTHORIZED` → `DEPLOY_STARTED` → 최종 사건이다.
90초 이상 건강 검사가 성공하면 `DEPLOY_COMPLETED`, 확인된 이전 버전 복구면
`DEPLOY_ROLLED_BACK`을 남긴다. 이 두 경우에만 주문 잠금을 해제한다. 최종 안전 상태를
증명하지 못하면 요청 파일은 폐기하지만 잠금은 `HALTED`로 유지하므로 자동 주문이
재개되지 않는다. 이 경로는 수동 주문, 시장가 주문, 가격 추격, 자본 증액, 전략 승격,
허용 종목 변경 또는 위험 관문 우회를 승인하지 않는다.

이전 긴급 시도가 확인된 `DEPLOY_ROLLED_BACK` 뒤 shell 정리만 실패했고, 그 뒤 정상
배포가 이미 정확한 최신 main을 90초 건강 검사와 함께 완료했다면 코드와 서비스를 다시
바꾸지 않는 cleanup-only 복구를 사용한다. 이전 파일·rollback 체인, rollback 기준부터
현재 main까지의 Git 계보, 현재 main의 유일한 정상 live 배포 완료, 그 사이 worker 시작,
현재 worker/timer 활성, 두 배타 잠금, KIS `open_unfilled=0`을 모두 확인한다. 새
`DEPLOY_EMERGENCY_AUTHORIZED`와 `DEPLOY_EMERGENCY_RECOVERY_COMPLETED`가 기록된 뒤에만
이전 요청과 유지보수 잠금을 제거한다. 한 증거라도 없으면 이전 잠금과 요청을 그대로 둔다.

## (B) 안전망 타이머 — `auto-invest-deploy.timer` (이미 설치됨)

`deploy/README.md` § 2 참고. 30분마다(장중 제외) `auto-invest-deploy.service` 를
실행. (A)가 어떤 이유로든 트리거 안 됐거나 장중 연기됐을 때 결국 최신 main 을
서버에 올리는 최종 보증.

## (C) 자율 튜너 타이머 — `auto-invest-tune.timer` (스펙 005 후속)

위 (A)/(B)는 **코드를 main 에서 서버로** 나르는 파이프라인이다. 이것과 **별개로**,
서버에 이미 올라간 코드(스펙 005 자율 튜너)가 **자기 설정을 측정 기반으로 조정**하는
오프아워 채널이 하나 더 있다. 코드 배포가 아니라 런타임 튜닝이라 (A)/(B)와 구분된다.

- **트리거**: `auto-invest-tune.timer` — 매일 22:00 UTC 1회(미국 장 마감 후).
  같은 oneshot `auto-invest-tune.service` 가 `deploy/run-tune.sh` 를 실행하고,
  그 안에서 이미 검증·머지된 `auto-invest tune --apply`(스펙 005 CLI)를 호출한다.
  **새 로직 없음** — 언제 돌릴지만 systemd 에 맡긴다.
- **무엇을 하나**: 롤링 윈도 KPI 를 읽어 저위험 L1 변경 한 종류 —
  `config/llm_kpi_thresholds.toml` 의 `tier_b` 임계값 조이기 — 만 자동 적용한다.
  적용 시 이전값을 담은 `AUTO_TUNED_L1` 감사 행이 남아 되돌릴 수 있다.
- **왜 안전한가**:
  1. **튜닝 ≠ 실거래 ≠ 코드 배포.** KPI 임계값(관측 기준선)만 조인다. 주문·포지션·
     워커 코드는 건드리지 않는다.
  2. **장중에는 0건 적용.** 타이머가 장 마감 후(22:00 UTC)에만 켜지고, 그래도
     튜너 자신의 `market_hours_guard`(헌법 VIII.A)가 한 번 더 막는다.
  3. **측정 부족이면 거부.** 윈도 표본 < 최소 표본이면 적용 안 함(헌법 X).
  4. **멱등.** 세션 날짜 기준 dedup — 같은 날 두 번 켜져도 한 번만 적용.
  5. **Kernel 은 절대 자동 적용 안 함.** 대상이 `kernel.toml` 에 닿으면 무조건
     L4 강등(자동 적용 거부 + 포렌식 콜아웃). 튜너는 헌법·kernel 을 쓰지 않는다.
  6. **DB 없으면 무동작.** `run-tune.sh` 는 텔레메트리 DB 가 없으면(새 인스턴스)
     조용히 종료 0 — 빨간 X 노이즈를 만들지 않는다.
- **운영자 확인**: `systemctl list-timers auto-invest-tune.timer`,
  `journalctl -u auto-invest-tune.service`. 적용 내역은 `audit_log` 의
  `AUTO_TUNED_L1` / `AUTO_TUNER_RUN` 행. 끄려면
  `systemctl disable --now auto-invest-tune.timer`.

이 채널은 헌법 X(측정 기반 자율 성장)가 정의한 "dry-run 워커로의 지속 배포" 안전
경계 **안에서** 동작한다 — 측정이 없으면 행동도 없고, 행동은 가역 L1 한 종류뿐이다.

## 운영자가 확인할 곳

- **즉시 결과**: GitHub Actions → "Deploy on merge to main" 실행 Summary.
- **서버 감사 추적**: 배포마다 `deploy correlation_id` 가 출력되고, 그 id 로
  `audit_log` 의 `DEPLOY_STARTED`/`DEPLOY_COMPLETED`/`DEPLOY_FAILED`/
  `DEPLOY_ROLLED_BACK` 행을 조인해 전말을 본다(`deploy/README.md` § 4).

## 사전 조건 (이미 충족되어 있어야 함)

- 저장소 시크릿: `VULTR_SSH_PRIVATE_KEY`, `VULTR_SSH_HOST`, `VULTR_SSH_USER`,
  `VULTR_SSH_KNOWN_HOSTS`, `VULTR_SSH_PORT` (trigger-design.yml 이 쓰는 것과
  동일). `VULTR_SSH_USER`는 root가 아니어야 한다.
- 인스턴스에 `deploy/repair-ssh-boundary.sh`로 forced-command deploy gateway가
  최초 설치되어 있어야 한다. 이후 helper/gateway 내용은 deploy service의
  `refresh-ssh-boundary-helpers.sh` pre-step이 main 기준으로 갱신한다. GitHub Actions는 gateway의 `sync-units`,
  `start-deploy`, `emergency-deploy`(오너 단회 승인 인자만), `deploy-journal`, 배포 DB 감사 전용 `deploy-audit`, KIS 조회 smoke 전용
  `kis-smoke` 고정 명령만 호출한다. `deploy-audit`는 선택적 16진수 correlation ID를 이중
  검증하고 root 소유 helper에서 `sqlite3 -readonly`만 실행한다. 돈 경로 관측 워크플로는
  `observe ...` 고정 명령만 호출한다. 여기에는
  페이퍼 전용 forward 트랙 실행·판정, 정지 깃발 조회, 계좌 NAV 조회, live growth
  읽기만 포함되며, live 무장·실주문·자본 변경 명령은 없다. `kis-smoke`는 40자리
  커밋 SHA만 인자로 받고, 서버의 root 소유 helper가 격리 checkout에서 읽기 테스트를
  실행한다.

## 이 파이프라인이 하지 않는 것

- 실거래 전환(`AUTO_INVEST_MODE=live`)을 이 파이프라인(A/B)이 켜지 않는다 — 코드만
  나르고 모드는 dry-run 그대로 둔다. 실거래 전환은 **별도의 가드형 go-live 채널**
  (`.github/workflows/go-live-canary.yml` → `deploy/go-live-canary.sh`)로만 이뤄진다.
  헌법 X.4(v4.0.0): 운영자 지시 시 그 가드형 채널로 **라이브 캐너리까지** 자율 전환
  가능(장중 가드·헬스체크·실패 시 dry-run 자동 복구·K1 캡 보존). 풀라이브 승격은
  여전히 별도 운영자 결정(헌법 VI 3단계). 운영자 지시가 없으면 절대 자동 전환 안 됨
  (스펙 005 튜너는 모드를 못 바꾼다).
- 헌법(`.specify/memory/constitution.md`)·Kernel 변경을 자동 배포 대상에서
  특별 취급하지 않는다(머지 단계의 포렌식 감사가 그 역할). 다만 그런 PR 의
  머지 자체는 K-meta 확인 규칙을 따른다(CLAUDE.md).
- 다중 호스트 오케스트레이션·임의 SHA 롤백 없음(spec 006 v1 범위 그대로).
