# auto-invest — 다음 세션 인수인계 (main 베이스라인)

이 파일은 이 저장소의 **`main` 브랜치에서 시작하는 모든 Claude 세션**의 진입점입니다. "지금 무슨 일이 일어나고 있는지"를 토큰 낭비 없이 빠르게 파악할 수 있도록 정리했습니다.

## 세션 시작 절차 (필수)

`CLAUDE.md`의 "운영자 응대 3대 규칙" + "Autonomous workflow policy"에 따라, 모든 새 세션은 계획을 세우거나 운영자에게 무엇을 할지 물어보기 **전에** 다음 발견 순서를 반드시 실행합니다:

```bash
# 1. origin의 모든 claude/* 브랜치 목록 — 진행 중인 작업이 여기 있습니다.
git fetch origin
git ls-remote --heads origin 'claude/*' | awk '{print $2}'

# 2. 열린 PR 목록 — 진행 중인 작업의 단일 진실의 원천.
#    mcp__github__list_pull_requests owner=jinooaction repo=claude state=open

# 3. 열린 PR이 진행 중인 브랜치를 가리킨다면, main에서 새 브랜치를 만들지 말고
#    그 브랜치를 체크아웃하세요.
git checkout <위에서 찾은 브랜치>
git pull --ff-only

# 4. 해당 브랜치의 HANDOFF-*.md 파일 (예: HANDOFF-008.md) — 작업 단위 상태.
```

## 운영자 응대 3대 규칙 (CLAUDE.md v3.2.0 — 절대 어기지 마세요)

1. **응답은 무조건 한글**. 새 세션 시작, 상태 보고, 작업 요약, 사과, 질문 — 예외 없음. 영어 응답은 운영자가 이해 못합니다.
2. **약어와 영어 비즈니스 용어 금지, 쉬운 한글로 풀어 써라**. 코드/식별자/파일 경로 같은 고유명은 그대로 두되 반드시 한글 설명을 옆에 붙입니다. 한 문장에 영어 단어 3개 이상이면 다시 씁니다.
3. **자동 머지** — 작업 완료 + 테스트 통과 + 린트 깨끗 + PR `mergeable_state=clean` 만족 시 운영자가 "머지해"라고 말하지 않아도 즉시 자동 머지. 매번 머지 명령 요청하는 것 자체가 헌법 IX.D가 제거하려던 동기 핸드오프 비용입니다.

상세 규칙은 `CLAUDE.md` 본문 참조.

## 현재 main 상태 (2026-05-15 기준)

* **헌법 v3.0.0** (2026-05-14 도입, 머지 커밋 `f849fab`). 원칙 IX.D — 운영자 자율 수행 보장. PR 생성과 머지는 모두 자동 워크플로우의 일부. Kernel 터치도 머지를 막지 않음. 안전 경계는 **생산 배포 단계**(스펙 007 하드닝 캐너리)에서 지킴.
* **스펙 001 (미국 주식 자동 거래 MVP)** — 출시 완료 (2026-05-04). 실제 KIS 브로커 검증 완료.
* **스펙 002 (토큰 사용량 측정)** — 출시 완료.
* **스펙 003 (세션 캐시)** — 출시 완료.
* **스펙 004 (LLM 판단 지점)** — 골격만. 구현 보류.
* **스펙 005 (자율 튜너)** — 골격만. 스펙 007 의존성은 이제 해소됨; 후속 구현 가능.
* **스펙 006 (배포 자동화 러너)** — **출시 완료** (2026-05-15, PR #7 머지 커밋 `790c0c1`). 38/38 작업 7단계 전부 완료. K4 터치 커밋 `c1800a6` (audit.py에 5종 새 이벤트 타입 추가). systemd 유닛/타이머 템플릿 동봉(`deploy/`).
* **스펙 007 (하드닝 캐너리 — 생산 배포 게이트)** — 출시 완료 (2026-05-14, PR #5 머지 커밋 `775f53a`). 40/40 작업 6단계 전부 완료.
* **스펙 008 (백테스트 엔진)** — 출시 완료 (2026-05-14, PR #4 머지 커밋 `7f8fb99`).
* **main의 테스트**: 617 통과, 1 스킵 (라이브 KIS 스모크는 `KIS_LIVE_TEST=1` 환경변수로 게이트).
* **린트**: `uv run ruff check src tests` 깨끗.
* **라이브 브로커 검증**: 운영자(mason)가 2026-05-04에 본인 실제 KIS 계좌에서 `scripts/live_smoke.py` 실행 — 검증 완료.

## 운영자 사용성 — 지금 바로 가능한 것

스펙 006이 출시되면서 운영자가 SSH로 들어가 git pull/restart를 손으로 안 해도 됩니다. PR #9로 시작 키트가 들어가서 운영자가 자기 호스트에서 한 줄 명령으로 자동 검증 + 정확한 systemd 명령을 받아볼 수 있습니다.

### 운영자 프로필별 진입점

| 운영자 상황 | 진입점 |
|------------|--------|
| **개발 지식 없음, Vultr 계정 보유** | `docs/OPERATOR_START_NONDEV_KR.md` — Vultr 서버 만들기부터 dry-run + 실주문 전환까지 한글 단계별 가이드. **자본금 100달러 + 1주일 dry-run 권장.** |
| **개발자, Linux/systemd 호스트 보유** | `docs/OPERATOR_START.md` — `git clone` → `.env` → `bash scripts/operator_install.sh` 5분 경로. |

### 운영자가 "굴리고 싶다 + 개발 지식 없음"이라고 답한 경우 (2026-05-15 세션)

운영자 환경: Vultr 계정, 자본금 100달러로 시작. 다음 세션이 도와드릴 때는:

1. `docs/OPERATOR_START_NONDEV_KR.md`를 처음부터 펴고, 운영자가 어느 단계에서 막혔는지 물어보세요. 단계 1~8 중 정확한 위치를 받아내야 합니다.
2. 운영자가 가져올 정보는 가이드 마지막 절 "다음 세션이 도와드리려면 가져올 것"에 명시되어 있습니다 (오류 메시지, 종료 코드, 로그 파일).
3. **자본금 100달러 안전 약속**과 **1주일 dry-run 안전 약속**을 운영자에게 매번 상기시키세요. 헌법 원칙 I-VII + VIII.A는 시스템이 지키지만, "자본금을 너무 빨리 늘리지 않는다" 같은 운영 수칙은 운영자만 지킬 수 있습니다.

### 개발자용 5분 경로

```bash
# 운영자 호스트 (Linux + systemd) 에서:
sudo install -d -m 0750 -o $(whoami) -g $(whoami) /opt/auto-invest
git clone https://github.com/jinooaction/claude.git /opt/auto-invest
cd /opt/auto-invest
uv sync
cp .env.example .env
nano .env                            # KIS_APP_KEY/SECRET/ACCOUNT_NO + AUTO_INVEST_CAPITAL
bash scripts/operator_install.sh     # 자동 검증 5단계 + sudo systemctl 명령 출력
# 출력된 sudo systemctl 명령 6줄 그대로 실행
```

`scripts/operator_install.sh`는 5단계 preflight를 수행합니다:

1. CLI 표면 확인 (`auto-invest --help`).
2. `.env`에 필수 키 4종(`KIS_APP_KEY`/`KIS_APP_SECRET`/`KIS_ACCOUNT_NO`/`AUTO_INVEST_CAPITAL`) 빈 값 아닌지.
3. SQLite 감사 로그 마이그레이션 적용.
4. 워커 dry-run — 브로커 호출 없이 룰 파일/캡 검증.
5. `auto-invest deploy --dry-run` — 배포 파이프라인 검증.

전부 통과해야만 systemd 명령을 출력하며, **root로 escalation은 절대 하지 않습니다** — 운영자가 출력된 명령을 검토한 다음 본인 손으로 실행합니다.

**즉시 사용 가능한 CLI**:

* `auto-invest run --dry-run --config tests/fixtures/rules/sample-canary.toml` — 브로커 안 건드리고 룰 검증.
* `auto-invest run --capital 10000` — 라이브 운영.
* `auto-invest deploy --dry-run` — 다음 배포가 무엇을 할지 미리 확인.
* `auto-invest deploy --branch main` — 실제 배포 (장중 자동 거부).
* `auto-invest backtest --rules config/rules.toml --from 2024-01-02 --to 2024-12-31` — 과거 데이터 백테스트.
* `auto-invest report --date 2026-05-04` — 일일 리포트.
* `auto-invest status` — 현재 상태 한 화면 JSON.

**다음 후보 (선택)**:

* **스펙 004 (LLM 판단 지점)** — Claude를 거래 결정 루프에 처음 끌어들이는 작업. 결정성을 일부 양보하고 추론 능력을 얻는 트레이드오프. 골격은 `specs/004-llm-judgment-points/spec.md`. 30일치 토큰 텔레메트리(스펙 002)가 쌓인 후 본격 구현 권장.
* **스펙 005 (자율 튜너)** — KPI 임계값을 자동으로 조정하는 작업. 스펙 007 캐너리가 게이트 역할을 하므로 이제 안전하게 진행 가능. 아직 골격만.

이 두 스펙은 "운영자 손이 더 줄지만 필수는 아니다" 영역. 위 한 줄 운영 절차만으로도 v1 자동 거래 서비스는 굴러갑니다.

## 출시된 기능 읽는 순서

1. `.specify/memory/constitution.md` — 헌법 v3.0.0, 원칙 IX.D 운영자 자율 수행 보장.
2. `.specify/memory/kernel.toml` — Kernel 매니페스트(고관심 포렌식 목록; v3.0.0에서 머지 차단 역할은 없음).
3. `CLAUDE.md` — 자동 워크플로우 + 자동 머지 + 한글 응답 정책. **PR을 열거나 머지하기 전에 반드시 읽으세요.**
4. `deploy/README.md` + `specs/006-deploy-automation/quickstart.md` — 운영자 systemd 설치 절차. **새 호스트에 올릴 때 첫 진입점.**
5. `specs/007-canary-hardening/` — 스펙 007 하드닝 캐너리 (생산 배포 게이트). `quickstart.md` 부터 시작.
6. `specs/008-backtest-engine/` — 스펙 008 백테스트 엔진. 캐너리의 핵심 의존성.

## 자동 머지 시스템 (v3.2.0 신설)

운영자가 매번 "머지해"라고 말하지 않아도 다음 조건이 모두 만족되면 즉시 자동 머지합니다:

1. 작업의 모든 후속 태스크 완료.
2. `uv run pytest` 통과 (skip 허용, fail 없음).
3. `uv run ruff check src tests` 깨끗.
4. PR `mergeable_state == "clean"`.
5. PR이 draft가 아니거나 ready로 전환 가능.

자동 머지 중단 조건은 좁습니다 — 헌법(`.specify/memory/constitution.md`) 변경 PR, 테스트 빨갛거나 mergeable_state 더러운 경우, PR 본문 "WIP" / "DO NOT MERGE" 표식, 운영자가 명시적으로 "머지하지 마" / "기다려" / "잠깐"이라고 한 경우.

상세 규칙은 `CLAUDE.md` § "운영자 응대 3대 규칙 — 규칙 3" 참조.

## 안전 불변량 (절대 협상 불가)

다음은 헌법 원칙 I-VII와 VIII.A로 보호되며, 어떤 자율 워크플로우 변경에도 영향받지 않습니다:

- 포지션 사이징 (개당 / 종목당 / 전체 한도)
- 화이트리스트 기본 거부 정책
- LLM은 미리 정의된 판단 지점에서만 호출
- 추가-전용 감사 로그
- 비밀 정보 격리 (KIS 키 등)
- 백테스트 → 캐너리 → 본 운영 단계 진행
- 외부 API 견고성
- 장중 배포 금지

이 불변량은 스펙 007 하드닝 캐너리에 의해 **생산 배포 경계**에서 강제됩니다 (라이브 워커가 새 코드를 받기 전에).

## 과거 인수인계 파일 (참고용)

- `HANDOFF-002-003.md` — 스펙 002/003/004/005/006/007 골격 + 헌법 v2.0.0 단계의 상태. v3.0.0 이전이므로 "운영자가 수동 머지" 가이드는 **사용하지 마세요**.
- `HANDOFF-008.md` — 스펙 008 작업 단계 상태. 스펙 008이 출시되어 더 이상 활성 작업 아님.

## 다음 세션이 하지 말아야 할 것

- 진행 중인 브랜치가 있는데 main에서 새 브랜치를 만들지 **마세요** (위 발견 순서가 이를 막아줍니다).
- 열린 PR + 활성 인수인계 파일이 다음 작업을 알려주고 있는데 운영자에게 "어떤 작업을 원하세요?"라고 묻지 **마세요**.
- 출시 완료된 스펙(001 / 002 / 003 / 006 / 007 / 008)의 소스를 운영자의 명시적 수정 지시 없이 건드리지 **마세요**.
- KIS 자격 증명을 어디에도 푸시하지 **마세요**. `.env`는 gitignore되어 있고, 라이브 테스트는 `KIS_LIVE_TEST=1`로 게이트됨.
- `main`에 직접 푸시하지 **마세요** (직접 푸시 금지; 모든 변경은 PR을 통해 머지).

## 한눈 요약표

| 항목 | 상태 |
|------|-------|
| 헌법 | v3.0.0 (IX.D 운영자 자율 수행 보장) |
| 운영자 응대 정책 | CLAUDE.md v3.2.0 (한글 응답 / 쉬운 한글 / 자동 머지) |
| 마지막 main 커밋 | `0501428 Merge PR #9: 운영자 시작 키트 + KIS_ACCOUNT_NO 통일` |
| 활성 작업 | 없음 (운영자 다음 지시 대기) |
| 출시 완료 스펙 | 001, 002, 003, 006, 007, 008 |
| 골격 스펙 | 004 (LLM 판단 지점), 005 (자율 튜너) |
| 비개발자 시작 가이드 (Vultr) | `docs/OPERATOR_START_NONDEV_KR.md` (한글, 단계별) |
| 개발자 5분 가이드 | `docs/OPERATOR_START.md` (한글) |
| 자동 검증 스크립트 | `scripts/operator_install.sh` (5단계 preflight) |
| 운영 호스트 진입점 | `deploy/README.md` (systemd 설치 절차) |
| main 테스트 | 617 통과, 1 스킵 |
| main 린트 | 깨끗 |
| 열린 PR | `mcp__github__list_pull_requests`로 확인 |
| 운영자 로컬 환경 | `uv` 가상환경, `gh` 인증 완료, KIS 키는 `.env`에 (운영자 머신에만) |
