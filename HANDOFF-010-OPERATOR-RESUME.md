# 다음 세션 인계 노트 — spec 010 라이브 진입 단계 (2026-05-20)

**목적**: 운영자(mason)가 다음 세션에서 똑같은 설명을 다시 듣지 않고, Claude(다음 세션)가 즉시 정확한 다음 단계를 안내할 수 있도록.

---

## 운영자가 지금까지 한 일

1. Vultr 인스턴스 `202.182.125.132` (Tokyo) 가동 — 2026-05-16.
2. `set_secrets.sh`로 KIS 키 3개 (`KIS_APP_KEY`, `KIS_APP_SECRET`, `KIS_ACCOUNT_NO`) 입력 완료.
3. `auto-invest.service` systemd로 dry-run 모드 가동 중.
4. journalctl 로그 확인 — 워커는 dry-run 검증 성공 후 정상 종료 패턴으로 동작 중 (실주문 안 나감, 안전).
5. spec 010 자동 룰 설계자 + 후속 PR 3개 main 머지 완료 (#19, #20, #21, #22).
6. **막힌 곳**: `git pull` 실패 (detached HEAD 상태) — 운영자가 ANTHROPIC_API_KEY 추가하려고 `set_secrets.sh` 재실행 직전 단계.

## 운영자가 다음 세션에서 바로 칠 한 줄

Vultr 콘솔 "View Console" → root 로그인 후:

```bash
sudo -u auto-invest /usr/local/bin/uv run --project /opt/auto-invest auto-invest deploy --branch main \
  && sudo /opt/auto-invest/scripts/set_secrets.sh
```

이 한 줄이 하는 것:
1. **`auto-invest deploy --branch main`**: 시스템 정식 배포 함수로 main 최신 코드 받기 (git pull 대신 — detached HEAD 해결).
2. **`set_secrets.sh`**: 4개 prompt — KIS 3개 + 마지막에 ANTHROPIC_API_KEY.

그 후 한 줄 더:

```bash
sudo -u auto-invest /usr/local/bin/uv run --project /opt/auto-invest \
  auto-invest design --intent "자본 100달러, 미국 대형주 분산, 매주 월요일 적립, 위험 보통"
```

→ Claude 룰 자동 생성 → 검증 → `OK` 입력 → 자동 라이브 시작.

## 다음 세션에서 Claude(나)가 봐야 할 것

1. **이 파일** (`HANDOFF-010-OPERATOR-RESUME.md`) — 운영자 현 위치 확인.
2. `docs/OPERATOR_DESIGN_KR.md` — 운영자 가이드 (운영자에게 안내할 내용).
3. `HANDOFF.md` 본체 — Vultr 인스턴스 정보(IP `202.182.125.132`), set_secrets.sh 흐름.
4. PR 머지 이력 (`git log --oneline -20`) — spec 010 + 후속 작업이 main에 있는지 확인.
5. **운영자에게 묻지 말 것** — 아래 항목은 운영자가 이미 답했음:
   - "Vultr 인스턴스 있냐?" → **이미 가동 중** (`202.182.125.132`)
   - "KIS 키 있냐?" → **이미 입력됨**
   - "Claude API 키 있냐?" → **있음 (A로 답변)**
   - "어디서 거래 굴릴 거냐?" → **Vultr 인스턴스에서**

## 알려진 함정 (다음 세션에서 또 안 헷갈리도록)

1. **WARNING 잘못 알람**: `set_secrets.sh`의 `is-active` 체크가 dry-run 모드 정상 종료를 "실패"로 잘못 표시했음. 이번 PR(#23)에서 `journalctl`로 "Dry run successful." 흔적도 같이 확인하도록 수정. 다음 세션에서 운영자가 또 같은 WARNING 보면 — 코드가 안 받아진 것. `auto-invest deploy --branch main` 다시 실행.
2. **한글 깨짐**: Vultr 콘솔이 UTF-8 한글 폰트 없음. 출력의 `■` 같은 깨진 문자 = 한글. 동작은 정상. 가독성 문제는 별도 PR로 영문 병기 가능.
3. **detached HEAD**: `git pull` 직접 호출하면 "You are not currently on a branch" — `auto-invest deploy --branch main`을 대신 쓸 것.
4. **spec 008 의존성**: `verifier.py`가 백테스트 단계를 import 가드로 통과 처리 중 (spec 008 미완성). spec 008이 머지되면 자동 활성화.

## 다음 세션 추천 작업 (운영자가 추가 지시 없을 때)

운영자가 design 명령으로 라이브 시작 성공 → 1주일 관찰 → 그 후:

1. spec 008(백테스트 엔진) 완성 — 다른 브랜치 `claude/continue-work-ID7Ec`에서 진행 중. 머지 후 design 명령의 검증이 강화됨.
2. spec 007(hardened canary) 작성 — 운영자 OK 단계 자동화의 마지막 가드.
3. spec 005(autonomous tuner) 작성 — 시장 변화 따라 룰 자동 진화.

## main 상태 (2026-05-20 기준)

| 항목 | 값 |
|------|-----|
| 마지막 main commit | `5f10d49` (PR #22 ANTHROPIC 키 셋업) + 본 PR(#23) 머지 후 갱신 |
| 출시 완료 스펙 | 001, 002, 003, 006, 007, 008, 009, 010 |
| 스펙 010 핵심 commit | `b6442ee` (K4 페이로드 4종 additive) — 운영자 forensic 추적용 |
| 스펙 010 후속 commit | `d78d0ae` 라이브 worker 자동 시작, `167355c` --check 모드 |
| 테스트 | 733 passed (1 skipped — live KIS smoke) |
| 린트 | 깨끗 |

운영자 환경 진척:
- ✅ Vultr 인스턴스 가동
- ✅ KIS 키 입력
- ⏳ ANTHROPIC 키 입력 (다음 세션 시작 시 한 줄로 처리)
- ⏳ `auto-invest design` 첫 실행 (운영자가 ANTHROPIC 키 입력 후 바로)
- ⏳ 1주일 dry-run 관찰
- ⏳ live 모드 전환 (`AUTO_INVEST_MODE=live` 한 줄)
