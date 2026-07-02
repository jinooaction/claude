# Data Model: 운영자 대시보드와 모바일 알림 루프

## OperatorStatusReport

- `schema_version`: 보고서 계약 버전.
- `run_id`: workflow 또는 로컬 실행 식별자.
- `commit`: 보고서 생성 기준 commit.
- `timestamp_utc`: UTC 생성 시각.
- `overall_status`: `OK`, `ATTENTION`, `ACTION_REQUIRED`, `CRITICAL`.
- `headline_ko`: 모바일 첫 화면에 보일 한 줄 결론.
- `next_action_ko`: 운영자가 실제로 볼 다음 행동.
- `dashboard_url`: 상태판 URL. 없으면 생략 가능.
- `alert_decision`: `MobileAlertDecision`.
- `surfaces`: `OperatorSurface` 목록.
- `dashboard_sections`: 모바일 화면에 먼저 배치할 요약 묶음.
- `safety_invariants`: 이 보고서가 지키는 안전 불변조건.

## OperatorSurface

- `key`: 입력 표면 식별자. 예: `pipeline-liveness`, `money-path`.
- `source_ref`: 원천 sidecar 참조.
- `present`: 입력 파일 존재 여부.
- `parse_status`: `ok`, `missing`, `malformed`.
- `status`: 표면별 상태. 예: `OK`, `BLOCKED`, `CRITICAL`, `EXECUTION_READY`.
- `severity`: `info`, `attention`, `action`, `critical`.
- `summary_ko`: 운영자용 한 줄 요약.
- `next_action_ko`: 이 표면 때문에 필요한 행동. 없으면 빈 문자열.

## MobileAlertDecision

- `alert_level`: `SILENT_OK`, `ATTENTION_ONLY`, `ACTION_REQUIRED`, `CRITICAL`.
- `should_send`: Telegram 메시지 전송 여부.
- `reason_ko`: 왜 보내거나 보내지 않는지.
- `message_ko`: 전송할 text-only 메시지.
- `send_status`: workflow 전송 결과. 예: `NOT_ATTEMPTED`, `SENT`, `SKIPPED_MISSING_SECRETS`, `FAILED`.

## DashboardSection

- `key`: 화면 섹션 식별자.
- `title_ko`: 화면 제목.
- `status`: 섹션 상태.
- `body_ko`: 운영자 설명.
- `links`: 관련 GitHub Actions 또는 sidecar URL 목록.

## 상태 전이

1. 모든 필수 표면이 정상이고 개입 필요 상태가 없으면 `OK`.
2. 비핵심 보고 지연이나 정보 부족만 있으면 `ATTENTION`.
3. 돈 경로 차단, 자율 작업 실행 불가, 운영자 승인 필요, malformed 핵심 증거가 있으면 `ACTION_REQUIRED`.
4. pipeline liveness 핵심 루프 정지처럼 기존 생존 감시가 `CRITICAL`이면 `CRITICAL`.
