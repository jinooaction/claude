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

둘 다 같은 한 가지를 실행한다:
        `uv run auto-invest deploy --branch main`   (auto-invest-deploy.service)
        │
        ▼
spec 006 배포 상태기계 (안전 단계 전부 통과해야 워커 교체)
  preconditions(락) → 변경없음 검사(noop) → 장중 차단(market_hours_guard,
  헌법 VIII.A) → dirty tree → 시크릿 → git pull(origin/main) → kernel 확인 →
  [캐너리 게이트는 auto-tuner 트리거만] → sync → migrate → dry_run 검증 →
  worker restart → health_check(≥90초) → 실패 시 직전 good SHA 로 자동 롤백
```

(A)는 **즉시성**(머지 직후 몇 분 내 반영), (B)는 **안전망**(A가 실패하거나 머지가
장중에 일어났을 때 장 마감 후 자동 재시도)을 담당한다. 둘은 동일한 oneshot 서비스를
호출하므로 **안전 속성이 완전히 같다** — 어느 경로로 트리거되든 장중에는 배포되지
않고, 실패 시 롤백된다.

## 왜 이게 안전한가 (운영자 자율 수행 + 돈 안전 분리)

1. **배포 ≠ 실거래.** 현재 워커는 dry-run 모드(`AUTO_INVEST_MODE=dry-run`)다.
   배포는 코드를 교체하고 워커를 재시작할 뿐, 실주문을 내지 않는다. 실제 돈이
   움직이는 전환은 별도 게이트 `AUTO_INVEST_MODE=live` 토글이며 **운영자 명시
   지시가 있어야만** 바뀐다(이 파이프라인이 건드리지 않는다).
2. **장중에는 절대 배포 안 됨.** 타이머 달력이 미국 장시간(UTC 13~20시)을 빼고,
   그래도 `market_hours_guard`(헌법 VIII.A)가 DST 경계까지 한 번 더 막는다. 머지가
   장중에 일어나면 (A)는 "장중 연기"로 끝나고 (B) 타이머가 장 마감 후 올린다.
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

## (B) 안전망 타이머 — `auto-invest-deploy.timer` (이미 설치됨)

`deploy/README.md` § 2 참고. 30분마다(장중 제외) `auto-invest-deploy.service` 를
실행. (A)가 어떤 이유로든 트리거 안 됐거나 장중 연기됐을 때 결국 최신 main 을
서버에 올리는 최종 보증.

## 운영자가 확인할 곳

- **즉시 결과**: GitHub Actions → "Deploy on merge to main" 실행 Summary.
- **서버 감사 추적**: 배포마다 `deploy correlation_id` 가 출력되고, 그 id 로
  `audit_log` 의 `DEPLOY_STARTED`/`DEPLOY_COMPLETED`/`DEPLOY_FAILED`/
  `DEPLOY_ROLLED_BACK` 행을 조인해 전말을 본다(`deploy/README.md` § 4).

## 사전 조건 (이미 충족되어 있어야 함)

- 저장소 시크릿: `VULTR_SSH_PRIVATE_KEY`, `VULTR_SSH_HOST`, `VULTR_SSH_USER`,
  `VULTR_SSH_PORT` (trigger-design.yml 이 쓰는 것과 동일).
- 인스턴스에 `auto-invest-deploy.service` 설치 + SSH 사용자가 `sudo systemctl
  start` 권한 보유(operator_design.sh 가 이미 `sudo` 로 동작하므로 충족).

## 이 파이프라인이 하지 않는 것

- 실거래 전환(`AUTO_INVEST_MODE=live`)을 자동으로 켜지 않는다 — 운영자 전용.
- 헌법(`.specify/memory/constitution.md`)·Kernel 변경을 자동 배포 대상에서
  특별 취급하지 않는다(머지 단계의 포렌식 감사가 그 역할). 다만 그런 PR 의
  머지 자체는 K-meta 확인 규칙을 따른다(CLAUDE.md).
- 다중 호스트 오케스트레이션·임의 SHA 롤백 없음(spec 006 v1 범위 그대로).
