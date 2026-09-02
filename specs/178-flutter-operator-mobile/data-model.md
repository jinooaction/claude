# 자료 모델: 읽기 전용 Flutter 운영자 앱

## MobileStatusEnvelope

한 번의 Pages 실행에서 발행되는 최상위 자료다.

| 필드 | 형식 | 규칙 |
|------|------|------|
| schema_version | 문자열 | 첫 버전은 정확히 `1.0`; 상위 버전은 정상 해석 금지 |
| generated_at_utc | UTC 시각 | 파싱 가능하고 현재보다 미래가 아니어야 함 |
| repository | 문자열 | 공개 자료 출처 표시 |
| commit | 문자열 | 같은 실행의 기준 변경 식별자 |
| run_url | 문자열 또는 null | 읽기 전용 생성 실행 근거 |
| source | 문자열 | `automation sidecars` 등 원천 설명 |
| read_only | 불리언 | 반드시 `true` |
| liveness | LivenessReport | 자동화 생존 상태 |
| operator_status | OperatorStatus 또는 null | 운영자 요약; 누락은 주의 이상 |

## LivenessReport

| 필드 | 형식 | 규칙 |
|------|------|------|
| schema_version | 문자열 | 입력 보고 형식 버전 |
| as_of_utc | UTC 시각 | 평가 기준 시각 |
| overall | 문자열 | `HEALTHY`, `DEGRADED`, `CRITICAL` 계열 원문 보존 |
| checks | AutomationCheck 목록 | 식별자 중복 금지 |

## AutomationCheck

| 필드 | 형식 | 규칙 |
|------|------|------|
| key | 문자열 | 비어 있지 않고 목록 안에서 고유 |
| status | 문자열 | 원문 보존; 알 수 없으면 앱에서 주의 이상 |
| critical | 불리언 | 핵심 자동화 여부 |
| age_hours | 숫자 또는 null | 음수 금지; null은 신선함을 뜻하지 않음 |
| max_age_hours | 양수 | 허용 신선도 |
| timestamp_utc | UTC 시각 또는 null | null은 누락 상태 |
| detail | 문자열 | 비밀 없는 한글 설명 |

## OperatorStatus

| 필드 | 형식 | 규칙 |
|------|------|------|
| schema_version | 문자열 | 지원 버전 확인 |
| run_id | 문자열 | 공개 정제된 실행 식별자 |
| commit | 문자열 | 운영자 보고 기준 변경 |
| timestamp_utc | UTC 시각 | 보고 시각 |
| overall_status | 문자열 | 원문 보존 |
| headline_ko | 문자열 | 홈 최상단 핵심 설명 |
| next_action_ko | 문자열 | 운영자가 다음에 볼 대상 |
| dashboard_url | 문자열 또는 null | 원본 HTML 상태판 |
| dashboard_sections | DashboardSection 목록 | 네 핵심 영역 |
| surfaces | OperatorSurface 목록 | 원천별 판정 |
| safety_invariants | 문자열 목록 | 읽기 전용 경계 설명 |

## DashboardSection

`money`, `autonomous-work`, `alignment`, `action-needed`의 네 영역이다. 각 영역은
`key`, `title_ko`, `status`, `body_ko`를 가진다. 누락 영역은 앱에서 `UNKNOWN` 카드로 보존한다.

## CachedStatus

| 필드 | 형식 | 규칙 |
|------|------|------|
| raw_json | 문자열 | 마지막으로 완전히 검증된 원문만 저장 |
| saved_at_utc | UTC 시각 | 기기 저장 시각 |
| is_sample | 불리언 | 예제 자료 여부; 실제 화면에서 고정 배너 표시 |

## 앱 표시 상태 전이

```text
초기 → 불러오는 중
불러오는 중 → 최신 자료(네트워크 성공 + 계약·신선도 통과)
불러오는 중 → 오래된 자료(네트워크 성공 + 30시간 초과)
불러오는 중 → 오프라인 캐시(네트워크 실패 + 유효 캐시 존재)
불러오는 중 → 확인 불가(네트워크 실패 + 캐시 없음)
어떤 상태 → 새로고침 중 → 위 네 결과 중 하나
```

`오래된 자료`, `오프라인 캐시`, `확인 불가`, 계약 손상과 알 수 없는 상태는 신선한 정상으로
승격되지 않는다. 캐시에는 검증을 통과한 원문만 쓴다.
