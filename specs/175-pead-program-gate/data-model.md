# Data Model: PEAD와 21가족 프로그램 관문

## ProgramCalibrationExtension

| 필드 | 형식 | 규칙 |
|---|---|---|
| `gate_version` | 문자열 | `3.2` |
| `family_caps` | 객체 | `16: 0.010`, `64: 0.009` |
| `family_mix` | 객체 | `16: 11`, `64: 10` |
| `conservative_upper_bound` | 수 | 정확히 `0.200` |
| `diagnostic_program_null_rate` | 수 | 고정 난수 진단, 승격 근거 아님 |
| `calibrated` | 불리언 | 가족별 오합격·검출력·합계 모두 충족 |
| `capital_entry_eligible` | 불리언 | 항상 `false` |

가족 구성이 사전등록과 다르면 `calibrated=false`로 실패 폐쇄한다. 기존 `3.1` 필드는 삭제하거나
의미를 바꾸지 않는다.

## PeadMonth

| 필드 | 형식 | 규칙 |
|---|---|---|
| `signal_name` | 문자열 | `EarningsSurprise` 또는 `AnnouncementReturn` |
| `portfolio` | 문자열 | `LS`만 허용 |
| `observed_month` | `YYYY-MM` | 신호별 고유·오름차순 |
| `return_decimal` | 수 | 유한한 월수익, 공개 CSV의 백분율을 100으로 나눔 |
| `long_count` | 정수 | 1 이상 |
| `short_count` | 정수 | 1 이상 |

두 신호의 공통 월만 결합하며 2024-12까지 있어야 한다. 원본 바이트의 SHA-256을 별도 품질
객체에 기록한다.

## PeadCandidate

| 필드 | 형식 | 규칙 |
|---|---|---|
| `candidate_id` | 문자열 | 16개 전역 고유 ID |
| `trial_index` | 정수 | 1..16 |
| `announcement_weight` | 수 | `0, 1/7, ..., 1` |
| `surprise_weight` | 수 | `1 - announcement_weight` |
| `sleeve_scale` | 수 | `0.5` 또는 `1.0` |
| `annual_cost_bps` | 정수 | 150 |
| `strategy_fingerprint` | 문자열 | 정책·자료·분할·비용·위약 조건 SHA-256 |

후보 수, ID 또는 지문이 중복되면 전체 가족을 무효 처리한다.

## PeadResult

| 영역 | 핵심 필드 |
|---|---|
| 동일성 | 코드 커밋, 자료 출시본·URL·SHA-256, 후보 ID·지문 |
| 분할 | 개발, 차단, 출판 후, 최근 시작·종료·월수 |
| 선택 | 개발 샤프만으로 선택한 후보, 모든 16개 개발 점수 |
| 통계 | 가족 PBO, 출판 후 PSR·연수익, 시대·36개월 묶음, 집중도, 낙폭 |
| 강건성 | 연 300·500bp 비용, 부호 반전 위약시험 |
| 판정 | `PUBLISHED_EDGE`, `PAPER_CHALLENGER`, `NO_FACTORY_EDGE`와 실패 관문 |
| 한계 | 사전 열람 오염, 비공개 홀드아웃 아님, 시점보존·실행 동등성 없음 |
| 안전 | 연구 캐너리 false, 승격 false, 배포 null, 주문·자본 0 |

상태 전이는 `NO_FACTORY_EDGE/PAPER_CHALLENGER -> PUBLISHED_EDGE`까지만 가능하다. 이 기능의
결과에서 `FACTORY_EDGE` 또는 자본 진입 상태로 전이하는 경로는 없다.

## ResearchFamilyAuditRow

기존 행 형식을 재사용해 이전 800행 뒤에 PEAD 16행을 추가한다. 독립 소비자는 원시 행에서
후보 ID·지문 고유성, 가족 21개, 가족 크기 `16:11, 64:10`을 재구성한다. 생산자가 적은 요약값은
검증 근거로 사용하지 않는다.

## ForwardObservationState

| 필드 | 초기값 | 완료 조건 |
|---|---:|---|
| `start_date` | `2026-09-01` | 고정 |
| `required_earnings_events` | 200 | 시점보존 이벤트 누적 |
| `observed_earnings_events` | 0 | 실제 새 공시만 증가 |
| `required_calendar_months` | 12 | 경과 월수 |
| `observed_calendar_months` | 0 | 미래 관찰만 증가 |
| `point_in_time_constituents` | false | 당시 정보로 재구성 |
| `delisting_adjusted_returns` | false | 상장폐지 포함 가격 |
| `account_execution_parity` | false | 정수주·공매도·현재 비용 재현 |
| `eligible_for_next_review` | false | 모든 조건 충족 후 별도 검토 |

역사 최근성 검사는 2016-01~2024-12의 정확히 108개월을 겹치지 않는 36개월 세 구간으로
나눈다.
