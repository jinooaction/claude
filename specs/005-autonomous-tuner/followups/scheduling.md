# Spec 005 후속 — 자율 튜너 스케줄 연결 (off-hours 타이머)

상태: 구현 완료 (이 브랜치). 새 스펙이 아니라 스펙 005 CLI 의 **운영 연결**이다.

## 무엇 / 왜

스펙 005 는 `auto-invest tune --apply`(저위험 L1 자동 적용) CLI 를 완성했지만,
실행은 **수동/단발**이었다(운영자가 직접 또는 cron 으로 1회). HANDOFF-016 후속 #2
("튜너를 거래 루프/타이머에 연결")를 채워, 라이브(dry-run) 워커가 도는 인스턴스에서
튜너가 **세션 마감 후 매일 자동으로** 돌게 한다 — "자율 튜너"의 자율을 실제로 켠다.

## 설계 결정 — 워커 내부 훅이 아니라 외부 oneshot 타이머

후보 두 가지:

- (a) 워커 루프(`worker/loop.py`) 안에서 세션 마감 전이 때 튜너 호출.
- (b) **외부 systemd oneshot 타이머**가 기존 `auto-invest tune --apply` CLI 를 실행. ← 채택

(b)를 택한 이유:

1. **라이브 거래 경로(워커 코드)를 한 줄도 안 바꾼다.** 블래스트 반경 최소.
2. 저장소에 이미 있는 오프아워 타이머 패턴(`auto-invest-deploy.timer`)을 그대로
   미러링 — 운영자가 이미 아는 설치/검증 절차, 새 개념 0.
3. 이미 검증·머지된 CLI 를 재사용 — 새 적용 로직 0.

## 산출물

- `deploy/run-tune.sh` — 래퍼(`run-worker.sh` 미러). DB 없으면 종료 0(fail-safe).
- `deploy/auto-invest-tune.service` — oneshot(`auto-invest-deploy.service` 미러).
- `deploy/auto-invest-tune.timer` — 매일 22:00 UTC(미국 장 마감 후), `Persistent=true`.
- `deploy/vultr-userdata.sh` — 유닛 설치 + 타이머 즉시 활성.
- `deploy/README.md`, `deploy/AUTO-DEPLOY.md` — 설치·안전 설명((C) 채널).
- `tests/unit/test_tune_timer.py` — 산출물 검증(오프아워·CLI 호출·fail-safe).

## 안전 경계 (이 후속이 바꾸지 않는 것)

- **Kernel 터치 0건.** 손댄 파일 전부 `deploy/`·`tests/`·`specs/`. K1~K6·K-meta 무관.
- 적용 안전성은 전부 튜너 자신(스펙 005)이 보장: L1 한 종류·가역, 장중 0건 적용
  (헌법 VIII.A), 측정 부족 거부(헌법 X), 멱등, kernel 대상은 L4 거부.
- 타이머는 코드 배포가 아니라 **런타임 KPI 임계값 튜닝**이다. 주문·포지션·실거래
  토글(`AUTO_INVEST_MODE=live`)과 무관 — 실거래 전환은 여전히 운영자 전용.
- 헌법 X 의 "측정 → 행동" 루프를 dry-run 워커 안전 경계 안에서 자동화할 뿐이다.
