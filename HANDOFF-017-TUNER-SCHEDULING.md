# HANDOFF 017 — 스펙 005 후속: 자율 튜너 오프아워 타이머 연결

작성: 2026-05-26 (PR #63 머지 직후, main `92dd0ff`)
다음 세션이 `git fetch origin` + main 의 HANDOFF-*.md 발견 단계에서 이 파일을 자동 발견합니다.

## 한 줄 요약

**자율 튜너(스펙 005)를 매일 장 마감 후 자동 실행되도록 연결했습니다.** 스펙 005는
`auto-invest tune --apply`(저위험 L1 자동 적용) CLI 를 완성했지만 실행은 수동/단발
이었습니다. HANDOFF-016 후속 #2("튜너를 거래 루프/타이머에 연결")를 채워, 라이브
(dry-run) 워커가 도는 인스턴스에서 튜너가 **세션 마감 후 매일 자동으로** 돌게 했습니다 —
'자율 튜너'의 자율을 실제로 켰습니다. 헌법 원칙 X(측정 → 행동 루프)를 dry-run 워커
안전 경계 안에서 자동화한 것입니다.

## 설계 결정 — 워커 내부 훅이 아니라 외부 oneshot 타이머

후보 둘:

- (a) 워커 루프(`worker/loop.py`) 안에서 세션 마감 전이 때 튜너 호출.
- (b) **외부 systemd oneshot 타이머**가 기존 `auto-invest tune --apply` CLI 를 실행. ← 채택

(b)를 택한 이유:

1. **라이브 거래 경로(워커 코드)를 한 줄도 안 바꾼다.** 블래스트 반경 최소.
2. 저장소에 이미 있는 오프아워 타이머 패턴(`auto-invest-deploy.timer`)을 그대로
   미러링 — 운영자가 이미 아는 설치/검증 절차, 새 개념 0.
3. 이미 검증·머지된 CLI 를 재사용 — 새 적용 로직 0.

## 무엇을 만들었나

- `deploy/run-tune.sh` — 래퍼(`run-worker.sh` 미러). `AUTO_INVEST_DB`(기본
  `data/auto_invest.db`)·`AUTO_INVEST_REPORTS`(기본 `reports`)를 읽어
  `auto-invest tune --apply --db ... --output-root ...` 실행. **텔레메트리 DB 가
  없으면(새 인스턴스) 종료 0**(fail-safe, 매일 빨간 X 안 만듦).
- `deploy/auto-invest-tune.service` — oneshot(`auto-invest-deploy.service` 미러).
  비밀키 불필요(순수 결정론적, LLM 미호출)라 `EnvironmentFile=-`(선택).
- `deploy/auto-invest-tune.timer` — `OnCalendar=*-*-* 22:00:00`(미국 장 마감 후,
  EDT 20:00 / EST 21:00 UTC 둘 다 이후), `Persistent=true`(호스트 다운 시 부팅 후 보충).
- `deploy/vultr-userdata.sh` — 유닛 설치 + `systemctl enable --now
  auto-invest-tune.timer`(즉시 활성, 키 불필요).
- `deploy/README.md` § 2·3·6 + `deploy/AUTO-DEPLOY.md` (C) 절 — 설치·검증·안전 설명.
- `tests/unit/test_tune_timer.py` — 산출물 검증 8건: 파일 존재, 래퍼가 검증된 CLI 를
  `--apply`로 호출, DB-없음 fail-safe, 실행권한, 서비스 oneshot, 타이머 오프아워
  (UTC 13~20시 회피)·`Persistent`·daily, cloud-init 설치 배선.
- `specs/005-autonomous-tuner/followups/scheduling.md` — 설계·안전 기록.

## 안전 경계 (이 후속이 바꾸지 않는 것)

- **Kernel 터치 0건.** 손댄 파일 전부 `deploy/`·`tests/`·`specs/`. K1~K6·K-meta
  무관, 헌법·`kernel.toml` 무변경.
- 적용 안전성은 전부 튜너 자신(스펙 005)이 보장:
  1. 저위험 **L1 한 종류**(`config/llm_kpi_thresholds.toml` 의 `tier_b` 조이기)·가역
     (이전값 `AUTO_TUNED_L1` 감사 행에 남음).
  2. **장중 0건 적용** — 타이머가 장 마감 후(22:00 UTC)에만 켜지고, 튜너의
     `market_hours_guard`(헌법 VIII.A)가 한 번 더 막음.
  3. **측정 부족 거부** — 윈도 표본 < 최소 표본이면 적용 안 함(헌법 X).
  4. **멱등** — 세션 날짜 dedup, 같은 날 두 번 켜져도 한 번만.
  5. **Kernel 대상은 L4 거부** — 대상이 `kernel.toml`에 닿으면 자동 적용 거부.
- 타이머는 **코드 배포가 아니라 런타임 KPI 임계값 튜닝**이다. 주문·포지션·실거래
  토글(`AUTO_INVEST_MODE=live`)과 무관 — 실거래 전환은 여전히 운영자 전용.
- 테스트 895 통과·4 스킵(라이브 KIS 가드), 린트 clean.

## 다음 세션이 할 수 있는 일 (HANDOFF-016 후속 후보 갱신)

1. **L1 적용 표면 확장** — 모델 라우팅·캐시 TTL 노브. **주의: K3 인접**(LLM 비용=헌법
   III가 "자율 배포가 LLM 비용을 무한정 키우지 못하게" 경계하는 바로 그 표면).
   자동 적용은 안전 경계상 신중해야 하고, 튜닝 대상 설정(캐시 TTL 등)이 아직
   TOML 노브로 존재하지 않아 새로 만들어야 함 — 운영자와 방향 확인 권장.
2. **L2/L3 → 캐너리 자동 큐** — 튜너가 기록만 하는 L2/L3 후보를 스펙 007 캐너리에
   자동 투입. 더 큰 다운스트림 스펙.
3. **운영 관찰** — 타이머가 켜진 인스턴스에서 `journalctl -u auto-invest-tune.service`
   + `audit_log` 의 `AUTO_TUNED_L1`/`AUTO_TUNER_RUN` 행으로 실제 자율 튜닝이 일어나는지
   확인(측정 데이터가 충분히 쌓인 뒤부터 의미 있음).
4. **실거래 전환** — `AUTO_INVEST_MODE=live`(운영자 명시 지시 필요, 돈 움직임).
