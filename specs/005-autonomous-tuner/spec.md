# Feature Specification: Autonomous Tuner (자율 튜너)

**Feature Branch**: `claude/wonderful-brown-dkVmU`
**Spec Directory**: `specs/005-autonomous-tuner/`
**Created**: 2026-05-06 (stub) · **Promoted**: 2026-05-24
**Status**: Implemented (2026-05-24, 브랜치 `claude/wonderful-brown-dkVmU`. 22개 작업 전부 완료, 튜너 테스트 40개 + 전체 887 통과·4 스킵, 린트 깨끗. 본 스펙 승격 — 운영자 지시 2026-05-24로 텔레메트리 30일 착수 게이트 제거; 선행 스펙 006·007·011 충족)
**Input**: Operator description: "Close the measure → analyze → act loop. Detect KPI drift and apply changes autonomously within the boundary set by constitution principle IX (Self-Modification Boundary) and principle X (Measurement-Driven Autonomous Growth). Goal: zero operator merges except for Kernel changes."

## 배경 — 왜 이 스펙인가, 그리고 왜 지금 안전한가

지금까지의 시스템은 **측정**(스펙 002 토큰 텔레메트리, 스펙 011 라이브 성과)과 **판단**(스펙 004 LLM 판단 지점)을 갖췄지만, 그 측정 신호를 받아 **스스로 설정을 조정하는 행동(act)** 단계는 비어 있었다. 운영자가 KPI 표(`auto-invest efficiency`)와 성과 리포트(`auto-invest performance`)를 손으로 읽고, 손으로 임계값을 고쳐야 했다. 이 스펙은 그 마지막 고리 — 측정 → 분석 → 행동 — 을 **헌법이 정한 안전 경계 안에서** 닫는다.

핵심은 **권한 등급(tiered authority)** 이다. 모든 변경이 같은 위험을 갖지 않는다. KPI 임계값을 Tier B에서 Tier A 쪽으로 한 칸 조이는 것은 즉시 되돌릴 수 있는 저위험 행동이고, 포지션 캡(`risk/gates.py`, K1)을 건드리는 것은 실거래 손실 표면을 넓히는 고위험 행동이다. 자율 튜너는 이 둘을 **기계적으로 구분**해, 저위험은 즉시 자동 적용하고 고위험은 사람의 손(L4)으로 보낸다.

이것이 안전한 이유는 네 겹의 경계가 이미 깔려 있기 때문이다:

1. **헌법 IX (자기수정 경계) + `kernel.toml`** — "무엇이 Kernel인가"는 기계 판독 매니페스트가 단일 진실원이다. 튜너는 변경 대상 파일이 Kernel(K1~K6·K-meta)에 닿는지 매니페스트를 읽어 판정하고, 닿으면 분류 결과와 무관하게 **L4로 강제**한다(분류 오류에 대한 방어 심층화). 스펙 006의 배포 가드가 이미 같은 매니페스트를 읽는다(`deploy/kernel_guard.py`) — 재구현 금지, 재사용.
2. **헌법 X (측정 기반 자율 성장)** — 거래 성과를 겨냥한 어떤 자동 수정도 **상류 측정 신호 없이는 금지**다. 튜너는 행동 전 충분한 측정 증거(롤링 윈도 호출 수·성과 스냅샷)를 요구한다. thin 데이터에서의 튜닝은 거부된다.
3. **헌법 VIII.A (장중 배포 금지) + 스펙 007 하드닝 캐너리** — L1 자동 적용은 장 시간 여유 마진 밖에서만 일어난다. L2/L3(주문 행동에 닿는 변경)는 스펙 007 캐너리를 통과해야만 생산 워커에 도달한다 — 튜너는 캐너리에 후보를 *넣을* 뿐, 다일(multi-day) 캐너리를 동기적으로 통과시키지 않는다. 실제 머니 방어선은 머지 경계가 아니라 생산 배포 경계(IX.B-2)다.
4. **헌법 IV (추가-전용 감사)** — 튜너의 모든 행동(적용·후보 기록·거부·L4 콜아웃)은 추가-전용 감사 행으로 기록된다. 사후 분석이 "튜너가 무엇을 왜 했는가"를 빠짐없이 복원할 수 있다.

이미 존재하는 토대(재구현 금지): KPI 스냅샷(`telemetry/kpi.py`의 `compute_snapshot` + `telemetry/thresholds.py`의 `TierTable`), Kernel 매니페스트 리더(`deploy/kernel_guard.py`의 `load_kernel_manifest`/`KernelManifest.match`), 추가-전용 감사(`persistence/audit.py`의 `append` + pydantic 페이로드 패턴), 성과 측정(`performance/engine.py`의 `build_performance_report`), 장 시간 가드(`worker/schedule.py`), 일일 리포트(`reports/daily.py`).

## 권한 등급 모델 (헌법 v3.0.0 — 스텁에서 승계)

| 등급 | 예시 | 튜너 v1 행동 |
|------|------|-------------|
| **L1 (자동 적용)** | KPI 임계값을 자기 밴드 안에서 조정, 캐시 TTL, 모델 라우팅 같은 저위험·즉시 가역 노브 | 장 시간 마진 밖에서 즉시 적용. 스펙 007 캐너리 생략(저위험·즉시 가역). `AUTO_TUNED_L1` 감사. |
| **L2 (캐너리 통과 후 머지)** | 프롬프트 템플릿, 컨텍스트 압축 규칙, 판단 지점 파라미터, 비커널 의존성 업그레이드 | 튜너가 **후보로 기록**(`AUTO_TUNED_L2_CANARY_ENTERED`). 실제 승격은 스펙 007 하드닝 캐너리(≥30 거래일)가 별도로 수행. 튜너는 동기적으로 통과시키지 않음. |
| **L3 (캐너리 통과 후 머지, 더 넓은 범위)** | 새 판단 지점 선언, 새 비커널 SQLite 테이블, 새 스펙 골격 | L2와 같되 관측 윈도가 더 김(≥45 거래일). 튜너가 후보 기록만. |
| **L4 (인간 머지 필요 — Kernel)** | `kernel.toml`이 가리키는 모든 파일(K1~K6 + K-meta): 포지션 사이징, 화이트리스트, 판단 지점 계약, 감사 구조, 비밀 처리, 장 시간 가드, 매니페스트 자체, 헌법 | 튜너는 **자동 적용 거부**, 포렌식 콜아웃(`AUTO_TUNED_L4_FORENSIC`)을 감사·리포트에 남긴다. 튜너는 `kernel.toml` 자체를 절대 수정하지 않는다(K-meta). |

**경계 강제(방어 심층화)**: 변경 대상 파일 집합이 `kernel.toml` 매니페스트와 교집합을 가지면, 튜너가 그 변경을 어떻게 분류했든 **무조건 L4로 강등**된다. 분류 오류가 안전 경계를 넘지 못하게 하는 안전망이다.

## User Scenarios & Testing *(mandatory)*

<!-- 각 User Story 는 독립적으로 빌드·테스트·배포 가능한 슬라이스다. 하나만 구현해도 의미 있는 MVP 가 된다. -->

### User Story 1 — 튜너가 KPI 드리프트를 감지하고 권한 등급으로 분류한다 (Priority: P1)

자율 튜너가 거래 세션 마감 후 1회 실행되면, 기존 텔레메트리 KPI 스냅샷(`cache_hit_rate`·`usd_per_decision_mean`·`latency_p95_ms`·`tokens_per_decision_p95`)을 롤링 윈도(7일·30일)로 읽어 **탐지 규칙**을 돌린다. 각 탐지 규칙이 발화하면 하나의 **후보 변경(candidate change)** 을 만든다. 튜너는 각 후보가 건드릴 파일 집합을 `kernel.toml` 매니페스트(`deploy/kernel_guard.py` 재사용)에 비춰 **L1/L2/L3/L4 권한 등급으로 분류**한다. Kernel에 닿으면 분류와 무관하게 L4로 강등한다. 이 단계는 아직 아무것도 적용하지 않는다 — "튜너가 무엇을 하려는가"를 결정론적으로 산출하고 감사·리포트에 남긴다.

**Why this priority**: 이것이 자율 튜너의 안전 핵심이다. **무엇을 자동 적용해도 되고(L1) 무엇을 사람에게 보내야 하는가(L4)** 를 기계적으로 구분하는 분류 엔진이 없으면 어떤 자동 적용도 안전하지 않다. 이 슬라이스는 어떤 노브도 실제로 바꾸지 않으면서(read-only) 탐지+분류+감사 기계 전체를 만들고, 나머지 User Story가 이 위에 얹힌다. 결정론적으로 단독 테스트 가능. P1.

**Independent Test**: 합성 `token_usage` 행을 만들어 KPI가 특정 Tier에 들도록 한 뒤(예: `usd_per_decision_mean`이 Tier C 초과), `auto-invest tune --dry-run --as-of <date>`를 실행해 (1) 탐지 규칙이 올바른 후보를 만드는지, (2) 각 후보가 올바른 권한 등급으로 분류되는지, (3) 후보의 대상 파일이 `kernel.toml`에 닿으면 L4로 강등되는지, (4) dry-run에서는 어떤 파일도 수정되지 않고 후보 목록만 산출되는지 단독 검증.

**Acceptance Scenarios**:

1. **Given** 롤링-30일 `usd_per_decision_mean` 분포가 Tier B 안에서 안정적이고 Tier C 이벤트가 없음, **When** 튜너가 실행됨, **Then** "임계값 조이기(threshold tightening)" 후보가 `usd_per_decision_mean`에 대해 생성되고 `config/llm_kpi_thresholds.toml`을 대상 파일로 가지며 **L1로 분류**된다(그 파일은 Kernel이 아님).
2. **Given** 롤링-7일 `cache_hit_rate < 0.40`(Tier C), **When** 튜너가 실행됨, **Then** "캐시 미스 드리프트" 후보가 생성된다. 적용 가능한 노브가 v1에 없으면 후보는 **제안(proposal)으로 기록**되고 적용되지 않는다(아래 Assumptions의 노브 가용성 참조).
3. **Given** 어떤 후보의 대상 파일 집합이 `src/auto_invest/risk/gates.py`(K1)를 포함, **When** 튜너가 분류함, **Then** 그 후보는 튜너가 어떻게 분류했든 **L4로 강등**되고 `kernel_groups=["K1_position_sizing"]`가 후보에 기록된다.
4. **Given** `--dry-run` 플래그, **When** 튜너가 실행됨, **Then** 후보 목록·분류·근거가 산출되지만 **어떤 설정 파일도 수정되지 않고** 어떤 적용 감사(`AUTO_TUNED_L1`)도 기록되지 않는다.

---

### User Story 2 — 튜너가 저위험(L1) 변경을 자동 적용한다 (Priority: P1)

L1로 분류된 후보 중 **적용 경로가 정의된 노브**(v1: KPI 임계값 조이기)에 대해, 튜너는 `--apply` 모드에서 그 설정 변경을 실제로 적용한다. 적용은 **장 시간 마진 밖에서만**, **멱등(idempotent)** 하게 일어난다(이미 목표값이면 재적용 안 함). 적용 직후 `AUTO_TUNED_L1` 감사 행 1건이 탐지 규칙·KPI·대상 노브·이전값·새값·이전 Tier·새 Tier와 함께 기록된다. 변경은 추가-전용 감사로 완전히 가역적이다(이전값이 기록되므로 한 번의 역적용으로 되돌릴 수 있다).

**Why this priority**: 이것이 측정→분석→**행동** 루프를 실제로 닫는 절반이다. US1이 "무엇을 할지"를 산출한다면, US2는 그것을 안전한 한 노브에 대해 실제로 수행한다. KPI 임계값 조이기는 (a) 런타임에 실제로 읽히는 파일을 바꾸고, (b) 30일 안정성 증거에 기반하므로 헌법 X(측정 기반)를 만족하며, (c) 즉시 가역이라 L1로서 이상적이다. P1.

**Independent Test**: 롤링-30일 KPI가 Tier B 안에서 안정적인 합성 데이터를 만들고 `auto-invest tune --apply --as-of <date>`를 실행해, (1) `config/llm_kpi_thresholds.toml`의 해당 KPI 임계값이 Tier A 쪽으로 한 칸 조여지는지, (2) `AUTO_TUNED_L1` 감사 행이 이전값·새값과 함께 기록되는지, (3) 같은 명령을 다시 실행하면(멱등) 이미 목표값이라 재적용·재기록하지 않는지, (4) 장 시간 안(또는 마진 안)이면 적용을 건너뛰는지 단독 검증.

**Acceptance Scenarios**:

1. **Given** 롤링-30일 `latency_p95_ms`가 Tier B 안에서 안정적(Tier C 이벤트 0), **When** `tune --apply`가 장외에 실행됨, **Then** `config/llm_kpi_thresholds.toml`의 `latency_p95_ms` 임계값이 Tier A 쪽으로 정의된 스텝만큼 조여지고, `AUTO_TUNED_L1` 감사 행이 이전값·새값·근거와 함께 기록된다.
2. **Given** 직전 실행에서 임계값이 이미 목표값으로 조여짐, **When** `tune --apply`가 다시 실행됨, **Then** 튜너는 변경 없음을 감지해 재적용하지 않고 `AUTO_TUNED_L1`을 중복 기록하지 않는다(멱등).
3. **Given** L2/L3/L4로 분류된 후보, **When** `tune --apply`가 실행됨, **Then** 그 후보들은 **자동 적용되지 않고** 각각 캐너리 후보 기록(L2/L3) 또는 L4 포렌식 콜아웃으로만 처리된다.
4. **Given** 적용할 새값이 그 KPI의 밴드(Tier A 경계)를 넘어설 위험, **When** 튜너가 새값을 계산함, **Then** 새값은 Tier A 경계에서 클램프(clamp)되어 밴드를 넘지 않는다(안정성 보존 — 튜너가 자기 밴드 밖으로 임계값을 밀지 않음).

---

### User Story 3 — 안전 게이트: 장 시간 + 측정 기반(헌법 X) (Priority: P2)

튜너는 두 안전 게이트를 거친다. **(가) 장 시간 게이트** — 미국 정규장 개장 후 30분 이내, 또는 폐장 전 30분 이내에는 어떤 L1 적용도 거부한다(헌법 VIII.A 운영 마진). 기존 `worker/schedule.py`(K6)의 장 시간 판정을 **읽기만** 하고 수정하지 않는다. **(나) 측정 기반 게이트(헌법 X)** — 거래 성과를 겨냥한 튜닝은 상류 측정 신호가 충분할 때만 허용된다. 윈도 내 호출 수가 최소 표본 미만이거나 성과 스냅샷이 비어 있으면, 그 후보는 "측정 부족"으로 거부되고 그 거부가 감사에 기록된다. thin 데이터에서의 자동 튜닝은 금지다.

**Why this priority**: 헌법 VIII.A·X 준수를 코드로 강제한다. US1·US2가 동작해야 의미가 있으므로 그 위에 얹히는 P2. 단 이 게이트들은 **안전 불변량**이라 v1 출시에 반드시 포함된다.

**Independent Test**: (가) 장 시간 안의 시각으로 `tune --apply`를 호출해 적용이 거부되고 그 사실이 감사에 남는지, 장외 시각에는 적용되는지 단독 검증. (나) 윈도 내 호출 수가 최소 표본 미만인 합성 데이터로 튜너를 실행해 후보가 "측정 부족"으로 거부되고 감사에 기록되는지, 충분한 표본에서는 진행되는지 단독 검증.

**Acceptance Scenarios**:

1. **Given** 현재 시각이 미국 정규장 개장 후 15분(마진 30분 안), **When** `tune --apply`가 실행됨, **Then** 어떤 L1 적용도 일어나지 않고 "장 시간 마진"으로 건너뛴 사실이 감사에 기록되며 명령은 정상 종료(비정상 아님)한다.
2. **Given** 롤링 윈도 내 판단 호출 수가 선언된 최소 표본(예: 20) 미만, **When** 튜너가 성과 겨냥 후보를 평가함, **Then** 그 후보는 "측정 부족(헌법 X)"으로 거부되고 거부 사유가 감사에 기록되며 어떤 임계값도 변경되지 않는다.
3. **Given** 충분한 표본 + 장외 시각, **When** `tune --apply`가 실행됨, **Then** 두 게이트를 모두 통과해 L1 적용이 진행된다.

---

### User Story 4 — 운영자가 튜너 활동을 일일 리포트로 본다 + CLI (Priority: P2)

튜너는 매 실행마다 **`auto-tuner-report` JSON**을 일일 리포트 형제로 산출한다(`{output_root}/{session_date}/auto-tuner-report.json`). 이 리포트는 (1) 감지된 후보 변경 목록, (2) 각 후보의 권한 등급 분류와 근거, (3) 실제 적용된 L1 변경(이전값→새값), (4) 캐너리 후보(L2/L3) 목록, (5) L4 포렌식 콜아웃(Kernel 터치, 인간 머지 대기) 목록을 담는다. 운영자는 `auto-invest tune` CLI로 이를 구동한다 — `--dry-run`(적용 없이 후보만), `--apply`(L1 자동 적용), `--window`(롤링 윈도), `--as-of`(기준 날짜, 테스트·백필용), `--output-root`(리포트 위치), `--json`(stdout JSON).

**Why this priority**: 헌법 IV(감사) + 운영자 관측성 + 미래 자기 점검을 위해 필요하다. US1~US3가 산출하는 결정을 사람이 읽는 표면으로 노출한다. P2.

**Independent Test**: 합성 후보들을 만들고 `tune --dry-run --json`을 실행해 stdout JSON이 후보·분류·근거를 담는지, `--output-root`를 줬을 때 `auto-tuner-report.json` 파일이 그 날짜 하위에 써지는지, 적용된 L1 변경이 리포트의 `applied` 섹션에 이전값→새값으로 나타나는지 단독 검증.

**Acceptance Scenarios**:

1. **Given** 여러 후보가 감지·분류됨, **When** `tune --output-root data/reports --as-of <date>` 실행, **Then** `data/reports/<date>/auto-tuner-report.json`이 써지고 후보·분류·적용·캐너리 후보·L4 콜아웃 섹션을 포함한다.
2. **Given** `tune --json --dry-run`, **When** 실행, **Then** stdout에 기계 판독 JSON(후보 목록·분류·근거)이 출력되고 어떤 파일도 수정되지 않는다.
3. **Given** L1 변경 1건 적용 + L4 후보 1건 감지, **When** 리포트가 생성됨, **Then** `applied`에 L1 변경이 이전값→새값으로, `awaiting_human_merge`에 L4 후보가 대상 파일·Kernel 그룹과 함께 나타난다.

---

### Edge Cases

- **윈도에 데이터가 전혀 없음** → 모든 KPI가 `N/A`로 분류되고 어떤 후보도 생성되지 않으며, 튜너는 빈 리포트를 정상 산출(비정상 종료 아님).
- **KPI가 Tier C(나쁨)인데 적용 가능한 노브가 없음** → 후보는 "제안"으로 기록되되 적용되지 않는다(예: cost drift는 모델 라우팅 노브가 v1에 없으면 제안만).
- **임계값이 이미 Tier A 경계** → 더 조일 여지가 없으므로 후보 생성 안 함(클램프).
- **후보의 대상 파일이 Kernel + 비커널 둘 다 닿음** → Kernel 교집합이 하나라도 있으면 전체 후보가 L4로 강등.
- **`tune --apply`가 장 시간 안에 호출** → L1 적용 0건, "장 시간 마진" 스킵 감사, 정상 종료.
- **같은 세션에 튜너가 두 번 실행(멱등)** → 두 번째 실행은 이미 적용된 변경을 재적용·재기록하지 않는다.
- **`kernel.toml` 자체를 바꾸려는 후보** → K-meta. 튜너는 절대 생성하지 않으며, 외부에서 그런 후보가 주입돼도 L4 + "튜너는 K-meta를 수정하지 않음" 거부.
- **롤링-30일 안정성 판정 중 단 하나의 Tier C 이벤트** → 안정 아님으로 간주, 조이기 후보 생성 안 함(보수적).
- **성과 스냅샷이 손실(음수 PnL) 추세** → 성과 겨냥 튜닝(있다면)은 헌법 X에 따라 "측정이 개선을 지지하지 않음"으로 보류. v1의 임계값 조이기는 비용/효율 KPI 기반이라 PnL과 독립.

## Requirements *(mandatory)*

### Functional Requirements

#### 튜너 코어 (US1 — 탐지 + 분류)

- **FR-A01**: 튜너는 거래 세션 마감 후 1회 실행되도록 설계되며 **멱등(idempotent)** 하다 — 같은 입력·같은 상태에서 두 번 실행해도 부수효과(설정 변경·감사 행)가 한 번만 일어난다.
- **FR-A02**: 튜너의 모든 행동은 추가-전용 감사 행으로 기록된다(헌법 IV). 이벤트 타입은 행동 종류에 따라: `AUTO_TUNED_L1`(L1 적용), `AUTO_TUNED_L2_CANARY_ENTERED`(L2/L3 후보 캐너리 진입 기록), `AUTO_TUNED_L4_FORENSIC`(Kernel 터치 후보 포렌식 콜아웃), `AUTO_TUNER_RUN`(실행 요약). 전부 추가-전용.
- **FR-A05**: 튜너는 어떤 후보를 분류하기 전에 **반드시 `kernel.toml`을 (기존 `deploy/kernel_guard.py`로) 읽어** 후보의 대상 파일이 Kernel에 닿는지 판정한다. 매니페스트와 교집합을 가지는 후보는 분류와 무관하게 **L4로 강제**된다(방어 심층화).
- **FR-A06**: 튜너는 `kernel.toml` 자체(K-meta)를 **절대 수정하지 않는다**. Kernel에 파일을 추가하는 것(전방 호환 안전 개선)조차 L4(인간 경로)로만 가능하며 튜너 자동 적용 대상이 아니다.
- **FR-A08**: 탐지 규칙은 기존 KPI 스냅샷(`telemetry/kpi.py` `compute_snapshot` + `telemetry/thresholds.py` `TierTable`)을 입력으로 한다. 새 텔레메트리·새 KPI 정의를 발명하지 않는다(재사용).
- **FR-A09**: 권한 등급 분류는 후보의 **대상 파일 집합 + 변경 종류**로 결정된다. 등급 정의는 단일 표(권한 등급 모델)에 모여 코드로 선언되며 조회 가능하다.

#### L1 자동 적용 (US2)

- **FR-A10**: L1로 분류되고 **적용 경로가 정의된 노브**에 대해, `--apply` 모드에서 튜너는 설정 변경을 실제로 적용한다. v1의 적용 가능 노브는 **KPI 임계값 조이기**(`config/llm_kpi_thresholds.toml`)다.
- **FR-A11**: 임계값 조이기 규칙 — 롤링-30일 동안 한 KPI 분포가 Tier B 안에서 안정적이고(Tier C 이벤트 0) 충분한 표본을 가지면, 그 KPI의 임계값을 **Tier A 쪽으로 정의된 스텝만큼** 조인다. 새값은 **Tier A 경계에서 클램프**되어 밴드를 넘지 않는다.
- **FR-A12**: 모든 L1 적용은 멱등하다 — 이미 목표값이면 재적용·재기록하지 않는다. 적용 시 `AUTO_TUNED_L1` 1건에 KPI·대상 노브(파일+키)·이전값·새값·탐지 규칙·이전 Tier·새 Tier·윈도·correlation_id를 기록한다.
- **FR-A13**: L1 변경은 가역적이다 — 감사 행에 이전값이 남으므로 한 번의 역적용으로 되돌릴 수 있다. (자동 롤백 로직은 v1 범위 밖이나, 가역성은 보장된다.)

#### 안전 게이트 (US3)

- **FR-A03**: 튜너는 미국 정규장 개장 후 30분, 폐장 전 30분 이내에는 어떤 L1 적용도 거부한다(헌법 VIII.A 운영 마진). 기존 `worker/schedule.py`(K6) 장 시간 판정을 **읽기만** 하고 수정하지 않는다. 거부 시 정상 종료하고 스킵 사유를 감사에 남긴다.
- **FR-A14**: 거래 성과를 겨냥한 어떤 튜닝도 상류 측정 신호가 충분할 때만 허용된다(헌법 X). 롤링 윈도 내 호출 수가 선언된 최소 표본 미만이거나 성과 신호가 비어 있으면 그 후보는 "측정 부족"으로 거부되고 감사에 기록된다.

#### 관측성·리포트·CLI (US4)

- **FR-A04**: 모든 L2/L3/L4 후보는 다음을 담는다: 발화한 탐지 규칙, 관측된 지표, 제안된 변경(설명 + 대상 파일), 권한 등급, (Kernel 터치 시) Kernel 그룹, 근거, 측정 참조.
- **FR-A07**: 튜너는 매 실행마다 일일 리포트 형제로 `auto-tuner-report` JSON을 산출한다: 감지된 후보 + 분류 + 적용된 L1 변경 + 캐너리 후보(L2/L3) + L4 포렌식 콜아웃(인간 머지 대기).
- **FR-A15**: 튜너는 `auto-invest tune` CLI로 구동된다: `--dry-run`(적용 없이 후보만), `--apply`(L1 자동 적용), `--window`(롤링 윈도, 기본 7d/30d 규칙별), `--as-of`(기준 날짜), `--output-root`(리포트 위치), `--json`(stdout JSON), `--db`(SQLite 경로). 검증 실패는 비정상 종료 코드.

### Key Entities *(데이터를 다루는 항목)*

- **Candidate Change (후보 변경)**: 탐지 규칙 1건의 발화 결과. id·탐지 규칙명·관측 지표(KPI·값·Tier)·제안된 변경(대상 파일 집합 + 변경 종류 + 이전값→새값)·근거·측정 참조를 갖는다. 분류 전 상태.
- **Authority Classification (권한 등급 분류)**: 후보에 부여된 L1/L2/L3/L4 등급 + 분류 근거 + (Kernel 터치 시) 매칭된 Kernel 그룹 목록. `kernel.toml` 교집합이 있으면 L4 강제.
- **Tunable Knob (튜닝 가능 노브)**: 적용 경로가 정의된 설정 지점. 대상 파일·키·등급·읽기/쓰기 함수·밴드(클램프 경계)를 갖는다. v1: KPI 임계값(`config/llm_kpi_thresholds.toml`).
- **Tuner Run Result (튜너 실행 결과)**: 한 번의 `tune` 실행 산출물. 후보 목록·분류·적용된 변경·스킵 사유(장 시간/측정 부족)·실행 요약. `auto-tuner-report.json`으로 직렬화.
- **AUTO_TUNED_\* audit rows**: 튜너 행동의 추가-전용 감사. `AUTO_TUNED_L1`·`AUTO_TUNED_L2_CANARY_ENTERED`·`AUTO_TUNED_L4_FORENSIC`·`AUTO_TUNER_RUN`. K4(추가-전용 감사) 터치 — 추가-전용 패턴(스펙 004·009·010과 동일).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-A01**: 튜너가 산출하는 후보 변경과 그 권한 등급 분류는 **결정론적**이다 — 같은 입력(KPI 스냅샷 + `kernel.toml`)에 대해 항상 같은 후보·같은 등급이 나온다(테스트로 검증).
- **SC-A02**: 대상 파일이 `kernel.toml`의 어떤 그룹에든 닿는 후보는 **100% L4로 분류**된다 — 튜너의 1차 분류가 무엇이든 Kernel 교집합이 있으면 L4. 합성 후보(K1~K6·K-meta 각각을 건드리는)로 전수 검증.
- **SC-A03**: `--dry-run` 모드는 **어떤 설정 파일도 수정하지 않고** 어떤 `AUTO_TUNED_L1` 적용 감사도 기록하지 않는다(파일 mtime + 감사 카운트로 검증).
- **SC-A04**: L1 임계값 조이기는 멱등하다 — 동일 입력에 `--apply`를 두 번 실행해도 설정 파일은 한 번만 바뀌고 `AUTO_TUNED_L1`은 한 번만 기록된다.
- **SC-A05**: L1 적용 후 새 임계값은 항상 그 KPI의 Tier A 경계 **안**에 있다(밴드 클램프) — 튜너가 자기 밴드 밖으로 임계값을 밀지 않는다.
- **SC-A06**: 장 시간 마진 안에서 `--apply`를 호출하면 L1 적용은 **0건**이고 스킵 사유가 감사에 남으며 명령은 정상 종료한다(헌법 VIII.A 준수).
- **SC-A07**: 롤링 윈도 표본이 최소 표본 미만이면 성과 겨냥 후보는 적용되지 않고 "측정 부족" 거부가 감사에 남는다(헌법 X 준수).
- **SC-A08**: `auto-tuner-report.json`의 적용 섹션 합과 그 실행에서 기록된 `AUTO_TUNED_L1` 감사 행 수가 일치한다(리포트 ↔ 감사 정합).
- **SC-A09**: 튜너는 `kernel.toml`을 **절대 수정 대상으로 삼지 않는다** — 어떤 입력으로도 튜너가 `kernel.toml`·`constitution.md`를 자동 적용하지 않는다(K-meta 보호, 테스트로 검증).

## Assumptions

- **착수 게이트 제거**: 운영자 지시(2026-05-24)로 "≥30일 텔레메트리 누적" 착수 게이트는 제거됐다. 단 **런타임 행동은 헌법 X(측정 기반)에 계속 종속** — FR-A14가 thin 데이터 튜닝을 거부한다. "코드를 언제 쓰기 시작하는가"(즉시)와 "튜너가 thin 데이터로 행동해도 되는가"(아니오)는 별개다.
- **기존 토대 재사용(재구현 금지)**: KPI 스냅샷(`telemetry/kpi.py`·`thresholds.py`), Kernel 매니페스트 리더(`deploy/kernel_guard.py`), 추가-전용 감사(`persistence/audit.py`), 성과 측정(`performance/engine.py`), 장 시간 가드(`worker/schedule.py`), 일일 리포트(`reports/daily.py`)를 재사용·확장한다. 새 텔레메트리·감사·Kernel 리더·장 시간 판정을 발명하지 않는다.
- **노브 가용성(v1 정직한 범위)**: v1의 **유일한 적용 가능 L1 노브는 KPI 임계값**(`config/llm_kpi_thresholds.toml`)이다. 이 파일은 런타임에 실제로 읽히고(`load_thresholds`), 조이기는 가역·저위험이라 L1로 이상적이다. 스텁이 언급한 다른 탐지 규칙(cost drift → 모델 라우팅 swap, cache miss → 캐시 TTL 연장)은 **대상 설정 노브가 v1 코드에 아직 없으므로** 튜너가 **감지·후보 기록만** 하고 적용하지 않는다. 모델 라우팅/캐시 TTL을 튜닝 가능 노브로 만드는 것은 후속 작업(L1 적용 표면 확장)이며, 이 스펙은 그 노브를 발명하지 않는다(스펙 005가 LLM 비용 표면 K3을 건드리지 않게 하는 의도적 경계).
- **L2/L3는 후보 기록만, 동기 캐너리 통과 안 함**: 튜너는 한 번의 세션-마감 실행이고, 스펙 007 하드닝 캐너리는 ≥30 거래일의 다일 프로세스다. 따라서 튜너는 L2/L3 후보를 **캐너리 진입 후보로 기록**(`AUTO_TUNED_L2_CANARY_ENTERED`)할 뿐, 캐너리를 동기적으로 돌려 통과시키지 않는다. 실제 캐너리 승격/실패(`CANARY_PASSED`/`CANARY_FAILED`)는 스펙 007 엔진(`canary/run.py`)이 별도로 수행한다.
- **L4는 자동 적용 거부 + 포렌식 콜아웃**: 헌법 v3.0.0에서 IX.B-4(L4=인간 머지)는 형식상 폐지됐고 L4는 "추가 감사 + PR 포렌식 콜아웃"을 뜻한다. 그러나 **튜너 프로세스 자체**는 Kernel을 자동 적용하지 않는다(FR-A06) — 튜너는 후보를 L4로 표시하고 포렌식 콜아웃을 남길 뿐, Kernel 파일을 쓰지 않는다. Kernel 변경은 운영자 지시 세션의 명시적 작업으로만 일어난다.
- **장 시간 판정 출처**: 미국 정규장 개장/폐장 판정은 기존 `worker/schedule.py`(K6)를 읽는다. 튜너는 그 파일을 수정하지 않는다(읽기 전용 의존).
- **성과 신호 출처**: 헌법 X 측정 게이트의 입력은 스펙 011 `performance/engine.py`의 `build_performance_report`와 KPI 스냅샷의 호출 수다. v1의 임계값 조이기는 비용/효율 KPI 기반이므로 PnL과 독립이지만, FR-A14의 최소 표본 게이트는 호출 수로 판정한다.
- **Kernel 터치**: 새 감사 이벤트 타입 추가(`AUTO_TUNED_*`)는 `persistence/audit.py`(K4) **추가-전용** 터치다. 기존 이벤트·행 미변경, 마이그레이션 불필요(스펙 004·009·010과 동일 패턴). PR 본문에 K4 커밋 해시를 명시한다. K1·K2·K3·K5·K6·K-meta 터치 0건이 목표.
- **결정성 우선**: 탐지 규칙·분류·임계값 조이기 스텝은 전부 **결정론적 규칙**이다. LLM은 이 스펙에서 호출되지 않는다 — 자율 튜너 v1은 순수 결정론적 분석/적용 엔진이다(판단 지점 호출은 스펙 004의 거래 루프에서, 튜너는 그 호출들의 *측정치*를 읽을 뿐).

## Out of Scope

- **모델 라우팅·캐시 TTL 노브 신설** — 이 스펙은 KPI 임계값 외 새 튜닝 노브를 만들지 않는다(LLM 비용 표면 K3을 건드리지 않으려는 의도적 경계). 후속 L1 적용 표면 확장.
- **동기 캐너리 통과** — 튜너는 L2/L3 후보를 기록만; 다일 캐너리 승격은 스펙 007 엔진이 별도 수행.
- **자동 롤백 로직** — L1 변경은 가역적(이전값 기록)이나, 자동 역적용은 v1 범위 밖.
- **Kernel 자동 수정** — 튜너는 Kernel 파일을 절대 쓰지 않는다(FR-A06). Kernel 변경은 운영자 지시 세션.
- **튜너가 PR을 자동 개설** — v1 튜너 프로세스는 git/GitHub 작업을 하지 않는다(분석·설정 적용·감사·리포트만). L4 후보는 포렌식 콜아웃으로 노출.
- **멀티 계정/멀티 전략 튜닝** — v1은 단일 운영자·단일 계정.
- **적대적 견고성**(오염된 텔레메트리 방어) — 후속 연구.
