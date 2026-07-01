# 데이터 모델: 자율 작업 실행 루프

## EvidenceSurface

| 필드 | 설명 |
|------|------|
| `key` | 입력 증거 이름 |
| `source_ref` | automation 브랜치와 파일 |
| `present` | 원문 존재 여부 |
| `parse_status` | `ok`, `present`, `missing`, `malformed` |
| `summary_ko` | 운영자가 읽는 짧은 요약 |

## WorkPacket

| 필드 | 설명 |
|------|------|
| `packet_id` | 후보와 출처에서 만든 안정 식별자 |
| `candidate_id` | 원천 후보 식별자 |
| `domain_key` | 작업 영역 |
| `title_ko` | 한글 제목 |
| `work_type` | 실행 유형 |
| `risk_grade` | 위험 등급 |
| `priority_score` | 정렬 점수 |
| `status` | `EXECUTION_READY`, `OPERATOR_APPROVAL_REQUIRED`, `SUPPRESSED`, `BLOCKED` |
| `reason_ko` | 선택 이유 |
| `next_action_ko` | 다음 Codex 작업 지시 문장 |
| `required_inputs` | 필요한 입력 증거 |
| `safety_boundary` | 자동화가 넘지 말아야 할 경계 |
| `source_refs` | 근거 sidecar 출처 |

## AutonomousWorkExecutionReport

| 필드 | 설명 |
|------|------|
| `schema_version` | 스키마 버전 |
| `run_id` | workflow 또는 로컬 실행 식별자 |
| `commit` | 실행 대상 commit |
| `timestamp_utc` | UTC 생성 시각 |
| `overall_status` | 선택 결과 |
| `selected_work` | 최고 우선순위 작업 패킷 |
| `ranked_work` | 실행 가능 후보 순위 |
| `suppressed_work` | 승인 필요 또는 억제 후보 |
| `evidence_surfaces` | 입력 증거 상태 |
| `safety_invariants` | 보존된 안전 불변조건 |
