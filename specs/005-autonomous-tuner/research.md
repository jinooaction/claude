# Phase 0 Research — Autonomous Tuner (스펙 005)

모든 결정은 기존 코드를 재사용하는 방향으로 수렴했다. 새 외부 의존성·새 안전 기계 장치를 발명하지 않는다.

## R-1: KPI 스냅샷 읽기 — 기존 `telemetry/kpi.compute_snapshot` 재사용

- **결정**: 롤링 윈도 KPI는 `compute_snapshot(conn, window_start_utc=, window_end_utc=, tiers=)`로 읽는다. 반환 `EfficiencySnapshot.kpis`는 `KPI(name, value: Decimal, tier, direction, threshold_used)` 리스트, `.call_count`는 표본 수.
- **근거**: `kpi.py` 도크스트링이 명시 — "byte-stable for same input rows (SC-T04) so 005's autonomous tuner can diff snapshots reproducibly." 이 함수는 스펙 005를 위해 결정론적으로 설계됐다.
- **대안 기각**: 직접 SQL 집계 — 중복·정의 분기 위험(헌법 X "one yardstick" 위반).

## R-2: Kernel 교집합 판정 — 기존 `deploy/kernel_guard` 재사용

- **결정**: 후보의 대상 파일 경로 리스트를 `kernel_diff_check(changed_paths, manifest)`에 넘겨 `KernelTouchReport`를 받는다. `.is_clean`이 False면(=Kernel 교집합 존재) 후보를 L4로 강등하고 `.touched_groups`를 후보에 기록.
- **근거**: IX.C — "Code that asks 'is this path Kernel?' MUST read the manifest; hard-coded paths are forbidden." `kernel_guard`가 이미 그 단일 진실원 리더다. 스펙 006 배포 가드와 같은 코드를 쓰면 분류 일관성이 보장된다.
- **대안 기각**: 튜너 자체 경로 매칭 — IX.C 위반(하드코딩), 매니페스트 드리프트 위험.

## R-3: 장 시간 마진 게이트 — 기존 `worker/schedule` 읽기 전용 재사용

- **결정**: `schedule.is_session_open(now)`가 True면 L1 적용 차단(정규장 전체 = VIII.A 최강 준수). 추가로 `now`가 `next_session_open(now)`의 30분 전 이내면 차단(개장 전 마진). 두 조건 중 하나라도 참이면 "market_hours" 스킵.
- **근거**: FR-A03은 "개장 후 30분/폐장 전 30분" 마진을 말하지만, **정규장 전체를 차단하면 그 두 위험 창이 자동으로 포함**되고 헌법 VIII.A("장중 배포 금지")를 글자 그대로 만족한다. 더 보수적 = 더 안전. `schedule`은 K6이므로 **읽기만** 한다(수정 0).
- **세부**: `now`는 함수 인자로 주입(테스트는 장중/장외 시각 주입, CLI는 `datetime.now(UTC)`). 폐장 후는 가장 안전한 시각이므로 차단하지 않는다(스펙 FR-A03의 "폐장 전 30분"은 장중에 포함됨).
- **대안 기각**: `schedule`에 `previous_close`/마진 헬퍼 추가 — K6 수정이 되어 불필요한 Kernel 터치 발생. 읽기 전용 재사용이 더 안전.

## R-4: L1 적용 노브 — KPI 임계값 조이기(`config/llm_kpi_thresholds.toml`)만

- **결정**: v1의 유일한 적용 가능 L1 노브는 `tier_b` 임계값 조이기다. 다른 탐지 규칙(cost/cache/latency drift)은 **감지·후보 기록만** 한다(적용 노브가 v1에 없음).
- **근거**: `config/` 실태 조사 결과, 런타임에 실제로 읽히는 튜닝 가능 설정 파일은 `llm_kpi_thresholds.toml`(`load_thresholds`)뿐이다. 모델 라우팅/캐시 TTL 전용 설정 파일은 존재하지 않는다 — 그것을 만드는 것은 LLM 비용 표면(K3 인접) 신설이라 스펙 005가 의도적으로 피한다(spec.md Out of Scope). 임계값 조이기는 (a) 실제 런타임 파일 변경, (b) 가역, (c) 저위험 → L1로 이상적.
- **대안 기각**: 모델 라우팅 노브 신설 — 범위 초과 + K3 인접 위험. cache TTL 노브 신설 — 스펙 003 표면 확장, 범위 초과.

## R-5: 임계값 조이기 수학 — `tier_b`를 `tier_a` 쪽으로 한 스텝, 클램프

- **결정**: 조이기는 **`tier_b` 경계만** 옮긴다. `tier_c`·`tier_a`는 외곽 레일로 고정.
  - `lower_is_better`(latency/usd/tokens, 밴드 `c>b>a`): `gap = tier_b - tier_a`; `new_b = tier_b - STEP_FRACTION*gap`. 항상 `> tier_a`(STEP_FRACTION<1).
  - `higher_is_better`(cache_hit_rate, 밴드 `c<b<a`): `gap = tier_a - tier_b`; `new_b = tier_b + STEP_FRACTION*gap`. 항상 `< tier_a`.
  - `STEP_FRACTION = 0.2`(gap의 20% 한 스텝). 클램프: `new_b`는 `tier_a`와 `tier_c` 사이에 엄격히 유지(밴드 순서 `ThresholdEntry` 검증 통과 보장).
- **근거**: `tier_b`가 "충분히 좋다"의 바(bar). 그것을 `tier_a` 쪽으로 올리면 같은 성능을 더 엄격히 평가해 시스템을 개선 압박. 한 스텝(20%)은 작고 가역적. SC-A05("새 임계값은 Tier A 경계 안") 자동 만족.
- **대안 기각**: tier_a까지 한 번에 = 너무 공격적. tier_a도 같이 옮기기 = 외곽 레일이 흔들려 분류 의미 불안정.

## R-6: 안정성 판정 — 30일 집계 Tier B + 일별 Tier C 없음

- **결정**: KPI가 "롤링-30일 Tier B 안에서 안정"인지는 두 조건으로 판정: (1) 30일 **집계** 스냅샷의 그 KPI tier == "B", (2) 30일 윈도를 일(day) 단위로 쪼개 데이터가 있는 모든 날의 그 KPI tier가 "C"가 **아님**(즉 A 또는 B). 둘 다 참이고 표본이 충분하면(R-7) 조이기 후보 생성.
- **근거**: spec.md Edge Case "롤링-30일 안정성 판정 중 단 하나의 Tier C 이벤트 → 안정 아님"을 직접 구현. 일별 판정은 `compute_snapshot`을 날짜별 윈도로 재호출(재사용). 집계가 이미 A면 조일 여지 없음(후보 생성 안 함).
- **대안 기각**: 집계만 보기 = 단일 나쁜 날을 가림(엣지 케이스 위반). 표준편차·분산 = 새 통계 정의 도입(불필요한 복잡도).

## R-7: 측정 기반 게이트(헌법 X) — 최소 표본

- **결정**: 조이기 후보는 윈도 `call_count >= MIN_SAMPLE`(기본 20)일 때만 진행. 미만이면 "insufficient_measurement"로 거부 + 감사 기록.
- **근거**: 헌법 X.1 "Measure before you tune. A tuning action with no upstream measurement signal is not permitted." thin 데이터에서의 조이기는 노이즈에 반응하는 것. 20은 보수적 하한(plan에서 상수로 노출, 후속 튜닝 가능).
- **대안 기각**: 게이트 없음 = 헌법 X 위반. 30일 절대 일수 게이트 = 운영자가 2026-05-24에 제거(착수 게이트). 표본 수 게이트는 런타임 행동 게이트라 헌법 X 하에 유지.

## R-8: 멱등성 — 세션 날짜 기반 감사 dedup

- **결정**: L1 적용 전 `audit_log`에서 `(event_type=AUTO_TUNED_L1, kpi_name, session_date)` 조합이 이미 있는지 조회. 있으면 skip(재적용·재기록 안 함). `session_date`는 `--as-of`(없으면 오늘).
- **근거**: FR-A01 "세션 마감 후 1회, 멱등." 같은 세션을 두 번 돌려도 한 번만. 조이기는 적용 후 임계값이 변하므로 값 비교만으로는 멱등하지 않다(재실행이 또 조임) — 세션-날짜 마커가 올바른 멱등 키.
- **대안 기각**: 값 비교 멱등 = 재실행이 누적 조이기(비멱등). 파일 mtime = 다른 변경에 취약.

## R-9: 리포트 — 일일 리포트 형제 JSON

- **결정**: `auto-tuner-report.json`을 `{output_root}/{session_date}/auto-tuner-report.json`에 쓴다(스펙 011 일일 리포트 `write_report` 경로 규칙 미러링). `--output-root` 미지정 시 파일 미작성(stdout `--json`만).
- **근거**: FR-A07. 운영자가 일일 리포트 옆에서 튜너 활동을 본다. 기존 리포트 디렉터리 레이아웃 재사용.

## R-10: 감사 이벤트 — K4 추가-전용 4종

- **결정**: `persistence/audit.py`(K4)에 `AUTO_TUNED_L1`·`AUTO_TUNED_L2_CANARY_ENTERED`·`AUTO_TUNED_L4_FORENSIC`·`AUTO_TUNER_RUN` 페이로드 4종 추가. `EventType` 리터럴 + `AnyPayload` union에 추가. 기존 행·타입 불변, 마이그레이션 불필요.
- **근거**: 스펙 004(`JUDGMENT_*` 2종)·009·010과 동일한 추가-전용 패턴. K4 터치는 forensic 콜아웃 대상이나 머지를 막지 않음(IX.B).
- **대안 기각**: 별도 SQLite 테이블 = 새 마이그레이션·새 K4 표면. 기존 감사 로그 재사용이 정합·단순.
