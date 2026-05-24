# HANDOFF 016 — 스펙 005 자율 튜너 출시

작성: 2026-05-24 (PR #60 머지 직후, main `0a176fb`)
다음 세션이 `git fetch origin` + main 의 HANDOFF-*.md 발견 단계에서 이 파일을 자동 발견합니다.

## 한 줄 요약

**측정 → 분석 → 행동 루프를 닫는 자율 튜너(스펙 005)를 완성·머지했습니다.** 그동안 시스템은 측정(스펙 002 토큰 사용량·011 라이브 성과)과 판단(스펙 004 LLM 판단 지점)은 갖췄지만 "측정 신호를 받아 스스로 설정을 조정하는 행동" 단계가 비어 있었습니다. 이 스펙이 그 마지막 고리를 **헌법 안전 경계 안에서** 채웁니다. 핵심은 **권한 등급(L1~L4)** — 저위험 변경은 즉시 자동 적용하고 고위험(Kernel) 변경은 사람의 손으로 보냅니다. 22개 작업 전부 완료, 튜너 테스트 40개 + 전체 887 통과·4 스킵, 린트 깨끗.

## 무엇을 만들었나

새 비커널 패키지 `src/auto_invest/tuner/`:

- `models.py` — frozen dataclass(CandidateChange·Classification·AppliedChange·TunerRunResult 등).
- `detect.py` — 탐지 규칙. 기존 `telemetry/kpi.compute_snapshot` 으로 7일/30일 롤링 윈도 KPI 를 읽어 후보 생성. `threshold_tighten`(30일 Tier B 안정 + 일별 Tier C 없음)은 적용 후보, `cost_drift`/`cache_miss`/`latency_degradation`(7일 Tier C 이하 드리프트)은 제안 후보.
- `classify.py` — 권한 등급 분류. 기존 `deploy/kernel_guard` 재사용으로 L1~L4 판정. **대상 파일이 `kernel.toml`(K1~K6·K-meta)에 닿으면 무조건 L4 강등**(방어 심층화). `kernel.toml`·헌법은 K-meta 로 절대 자동 적용 거부.
- `knobs.py` — KPI 임계값 조이기 수학(`tier_b` 를 `tier_a` 쪽으로 gap 의 20% 한 스텝, 밴드에서 클램프) + 원자적 TOML 쓰기(주석·다른 키 보존).
- `gates.py` — 안전 게이트. 장 시간 마진(`worker/schedule` 읽기 전용, 헌법 VIII.A) + 측정 기반 최소 표본(헌법 X).
- `report.py` — `auto-tuner-report.json` 직렬화(일일 리포트 형제).
- `runner.py` — 오케스트레이션. dry-run 은 순수 분석(무변경·벽시계 비의존·재현 가능), apply 만 게이트·멱등 dedup(세션 날짜)·실제 적용·감사 기록.

CLI: `auto-invest tune` (`--apply/--dry-run`·`--as-of`·`--window-short-days`·`--window-long-days`·`--min-sample`·`--output-root`·`--json`·`--db`·`--thresholds`·`--kernel`).

## 권한 등급 모델 (v1 행동)

| 등급 | 예시 | 튜너 v1 행동 |
|------|------|-------------|
| **L1** | KPI 임계값 등 저위험·가역 노브 | 장 시간 마진 밖·측정 충분·멱등 시 즉시 자동 적용. v1 적용 노브는 `config/llm_kpi_thresholds.toml` 의 `tier_b` 조이기 한 종류. |
| **L2/L3** | 프롬프트·판단 지점 파라미터(L2), 새 판단 지점·스키마(L3) | 후보로 **기록만**. 다일 캐너리 승격은 스펙 007 엔진이 별도 수행(튜너는 동기 통과 안 함). |
| **L4** | Kernel(K1~K6·K-meta) | 자동 적용 **거부** + 포렌식 콜아웃. 튜너는 `kernel.toml`·헌법을 절대 쓰지 않음. |

## 안전 설계 (이번 세션의 핵심)

1. **Kernel 교집합 = 무조건 L4.** 변경 대상 파일이 `kernel.toml` 매니페스트에 하나라도 닿으면 1차 분류와 무관하게 L4로 강등(`test_tuner_classify.py` 가 K1~K6·K-meta 전수 검증, SC-A02·A09).
2. **L1 은 단 한 종류, 가역, 클램프.** 임계값 조이기는 30일 안정성 증거(헌법 X)에 기반하고 Tier A 경계에서 클램프되며 이전값이 감사에 남아 되돌릴 수 있음.
3. **장 시간 게이트(헌법 VIII.A).** 정규장 중·개장 30분 전이면 L1 적용 0건. `worker/schedule`(K6) 읽기 전용.
4. **측정 기반 게이트(헌법 X).** 윈도 표본 < 최소 표본이면 거부. thin 데이터 튜닝 금지.
5. **dry-run 무변경.** 기본 모드는 파일·감사 0 변경, 벽시계 비의존이라 재현 가능(SC-A03).
6. **멱등.** 세션 날짜 기반 감사 dedup — 같은 날 두 번 돌려도 한 번만(SC-A04).
7. **LLM 미호출.** 튜너 v1 은 순수 결정론적 분석/적용 엔진. 판단 지점 호출(스펙 004)의 *측정치*를 읽을 뿐.

## Kernel 터치 (forensic)

- **유일한 터치: `src/auto_invest/persistence/audit.py`(K4), 커밋 `8bbfca2`.** 추가-전용 이벤트 4종(`AUTO_TUNED_L1`·`AUTO_TUNED_L2_CANARY_ENTERED`·`AUTO_TUNED_L4_FORENSIC`·`AUTO_TUNER_RUN`). 기존 이벤트 타입·row 미변경, 마이그레이션 불필요(스펙 004·009·010과 동일 패턴).
- K1·K2·K3·K5·K6·K-meta 터치 0건.

## 다음 세션이 할 수 있는 일

1. **L1 적용 표면 확장** — 모델 라우팅·캐시 TTL 을 튜닝 가능 노브로(스펙 005가 의도적으로 범위 밖에 둔 K3 인접 표면). 새 탐지 규칙은 이미 cost/cache/latency drift 가 후보를 만들고 있으나 적용 노브가 없어 제안으로만 기록됨 — 그 노브를 만들면 자동 적용으로 승격.
2. **튜너를 거래 루프/타이머에 연결** — 현재는 `auto-invest tune` 수동/cron 1회 실행. 세션 마감 후 자동 호출하도록 워커 스케줄에 붙이는 것은 후속.
3. **L2/L3 → 캐너리 자동 연결** — 현재 튜너는 L2/L3 후보를 기록만 함. 스펙 007 캐너리 엔진에 후보를 자동 투입하는 큐는 후속 스펙.
4. **실거래 전환** — `AUTO_INVEST_MODE=live` (운영자 명시 지시 필요, 돈 움직임).

## 안전 경계 (이번 세션 변경 없음)

- 코드 머지 ≠ 실거래. 생산 배포는 스펙 007 하드닝 캐너리 게이트(IX.B-2). 튜너의 런타임 튜닝 행동은 헌법 X(측정 기반)에 종속.
- 트레이딩 안전 invariant(포지션 캡·화이트리스트·append-only audit·market-hours guard) 전부 그대로.
- 테스트 887 통과·4 스킵(라이브 KIS 가드), 린트 clean.
