# Feature Specification: Operational Health Roll-up (`auto-invest health`)

**Feature Branch**: `claude/affectionate-mayer-Sax0o` (spec dir `013-operational-health`)
**Created**: 2026-05-26
**Status**: Draft
**Input**: User direction: "세계 최고 수준이 되기 위한 작업 우선순위 — 운영 관측·신뢰성 강화."

## 배경 (왜 이 기능인가)

오늘 시스템의 관측 표면은 전부 **흩어진 사후 분석 명령**이다: `status`(현재 스냅샷
일부), `report`(어제 일일 요약), `performance`(손익), `efficiency`(토큰 KPI),
`tune`(튜너 진단). "지금 이 시스템이 **건강한가**"를 한 화면으로 알려주거나,
모니터링·알림이 붙을 **종료 코드**로 표현하는 단일 표면이 없다. 운영자는 워커가
살아있는지, 정합성 검사가 깨졌는지, 최근 오류가 났는지, 활동이 멈췄는지를 알려면
여러 명령을 따로 돌려 머릿속에서 합쳐야 한다.

이 공백은 실거래 전환 전 **신뢰 기반**의 가장 큰 약점이다. 세계 최고 수준의 자율
운영 시스템은 "한 번의 호출로 건강 상태와 종합 판정을 내는" 표면을 반드시 가진다.

이 기능은 그 표면을 만든다: 기존 데이터(감사 로그·정합성 기록·포지션·halt 플래그·
워커 PID 파일·토큰 KPI)를 **읽기 전용**으로 종합해 개별 점검 결과와 **종합 판정
(정상/주의/위험)** 을 내고, 모니터링이 붙을 수 있는 **종료 코드**를 반환한다.

**핵심 안전 불변**: 이 기능은 **100% 읽기 전용**이다. 거래 워커 루프(`worker/loop.py`)를
한 줄도 바꾸지 않고, 감사 로그에 단 한 줄도 쓰지 않으며(append 0건), 어떤 상태
파일도 변경하지 않는다. Kernel(K1~K6, K-meta) 터치 0건. 거래 경로 블래스트 반경 0.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — 한 명령으로 종합 건강 판정을 본다 (Priority: P1)

운영자(또는 모니터링 크론)가 `auto-invest health` 를 돌린다. 시스템은 여러 모듈을
읽어 **개별 점검 결과**(워커 생존·halt·정합성·최근 오류·활동 신선도)와 그것을 합친
**종합 판정**(`OK`/`DEGRADED`/`CRITICAL`)을 한 화면에 보여준다. 종합 판정은 가장
나쁜 개별 점검 결과를 따른다(위험 > 주의 > 정상).

**Acceptance**:
- 모든 점검이 정상이면 종합 판정 `OK`, 종료 코드 `0`.
- 점검 중 하나라도 `DEGRADED`/`CRITICAL`이면 종합 판정이 그 최악값, 종료 코드 `1`.
- `--format json` 은 기계가 읽을 구조(스키마 버전 포함, byte-stable 정렬)를 낸다.
- `--format text`(기본)는 사람이 읽을 한글 라벨 + 최상단 종합 판정 줄을 낸다.

### User Story 2 — 워커 생존과 거래 중지 상태를 즉시 안다 (Priority: P1)

운영자가 "워커가 지금 살아있나? 거래가 멈춰있나?"를 묻는다. `health` 는 워커 PID
파일과 halt 플래그를 읽어 답한다.

**Acceptance**:
- PID 파일이 있고 그 프로세스가 살아있으면 `worker_liveness` = `OK (pid N)`.
- PID 파일이 없으면 `DEGRADED`(워커 미실행). PID 파일은 있으나 프로세스가 죽었으면
  `DEGRADED`(stale PID).
- halt 플래그가 있으면 `halt` = `DEGRADED`(거래 중지됨 + 사유). 없으면 `OK`.

### User Story 3 — 정합성·오류·정체를 신뢰성 점검으로 본다 (Priority: P2)

**Acceptance**:
- 마지막 정합성 결과가 `MISMATCH` → `reconciliation` = `CRITICAL`. `INCONCLUSIVE` →
  `DEGRADED`. `OK`이나 `--stale-hours`(기본 36)를 넘겨 오래됐으면 `DEGRADED`. 기록이
  아예 없으면 `DEGRADED`.
- 최근 24시간 내 `ERROR` 이벤트가 1건 이상이면 `recent_errors` = `DEGRADED`(건수 +
  마지막 메시지). 없으면 `OK`.
- 마지막 감사 이벤트가 `--stale-hours` 보다 오래됐으면 `activity` = `DEGRADED`(정체
  가능). 감사 로그가 비어있으면 `DEGRADED`.

### User Story 4 — 맥락 정보를 함께 본다 (Priority: P3)

판정에 직접 쓰이지 않는 **맥락**(오늘 주문 깔때기 건수, 보유 종목 수, 마지막 성과
스냅샷의 수익률·최대낙폭, 마지막 튜너 실행 시각, 마지막 캐너리 검증 결과)을 같은
출력에 함께 보여준다. 데이터가 없으면 해당 항목은 `null`/생략하고 절대 죽지 않는다.

## Functional Requirements

- **FR-H01**: `health` 명령은 점검 결과를 종합해 `OK`/`DEGRADED`/`CRITICAL` 한 값을 낸다.
- **FR-H02**: 종료 코드 — `OK`→0, `DEGRADED`/`CRITICAL`→1, 잘못된 호출(옵션 오류)→2.
- **FR-H03**: DB 파일이 없으면 연결을 만들지 않고(빈 DB 생성 금지) `CRITICAL`(db 없음),
  종료 코드 1.
- **FR-H04**: `--format json|text`, 기본 text. json 은 `schema_version` 포함, `sort_keys`.
- **FR-H05**: `--stale-hours`(기본 36)로 정합성/활동 신선도 임계값을 조정.
- **FR-H06**: **읽기 전용** — 명령 실행 전후 `audit_log` row 수 불변. `db.migrate` 호출
  금지(라이브 워커와 동시 실행 시 DB 손상 위험 회피); 0001 마이그레이션의 테이블만 읽는다.
- **FR-H07**: 판정에 필요한 "현재 시각"은 주입 가능(`build_health_report(now=...)`)해
  결정론적 테스트가 가능하다.

## Success Criteria

- **SC-H01**: 깨끗한 시스템(워커 살아있음·halt 없음·정합성 최근 OK·오류 0·활동 신선)
  에서 `health` 가 `OK` + 종료 코드 0.
- **SC-H02**: 정합성 `MISMATCH` 시드 시 종합 `CRITICAL` + 종료 코드 1.
- **SC-H03**: `health` 실행 후 `audit_log` row 수가 실행 전과 같다(append 0건).
- **SC-H04**: 같은 입력·같은 `now` → 같은 json 출력(결정론, byte-stable).

## 안전 경계 (불변)

- 읽기 전용. 거래 워커 루프 무수정. 감사 로그 append 0건. Kernel 터치 0건.
- 실거래 토글(`AUTO_INVEST_MODE=live`)과 무관 — 이 기능은 관측만 한다.
