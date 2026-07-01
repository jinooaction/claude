# 데이터 모델: 완료 후보 소비 및 차순위 자동 승격 루프

## ReleasedWorkEntry

- `entry_id`: 후보와 원천 spec로 만든 결정론적 식별자.
- `candidate_id`: 완료 후보 식별자.
- `status`: `released`.
- `source_spec`: 완료 후보를 선언한 spec 디렉터리.
- `source_file`: 후보 식별자가 발견된 파일.
- `reason_ko`: 완료 처리 사유.
- `released_at_utc`: 장부 실행 시각.

검증 규칙:

- `candidate_id`는 `candidate-` 접두사를 가져야 한다.
- `status`는 이번 스펙에서 `released`만 발행한다.
- 같은 후보와 같은 spec 조합은 한 번만 발행한다.

## ReleasedWorkReport

- `schema_version`: 보고 스키마 버전.
- `run_id`: workflow 실행 식별자.
- `commit`: 실행 대상 main commit.
- `timestamp_utc`: 보고 생성 시각.
- `overall_status`: `OK` 또는 `EMPTY`.
- `released_work`: `ReleasedWorkEntry` 목록.
- `scanned_specs`: 스캔한 spec 디렉터리 수.
- `safety_invariants`: 읽기 전용 안전 경계 문구.

상태 전이:

1. 완료 spec 없음 또는 명시 후보 없음 -> `EMPTY`.
2. 하나 이상 완료 후보 발견 -> `OK`.
3. malformed 파일은 건너뛰고 다른 완료 후보 스캔은 계속한다.

## WorkPacket 완료 소비

- 입력 candidate가 완료 장부에 있으면 status는 `RELEASED`가 된다.
- `RELEASED` packet은 `ranked_work`가 아니라 `suppressed_work`에 들어간다.
- 선택 후보는 남은 `EXECUTION_READY` packet 중 우선순위가 가장 높은 항목이다.
