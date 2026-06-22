# Feature Specification: Telegram Server Connection Workflow

**Feature Branch**: `Codex/telegram-server-connect`  
**Created**: 2026-06-22  
**Status**: Draft  
**Input**: Operator has already provided `chat_id` and wants the remaining Telegram server connection work made easy without manual `.env` editing.

## User Scenarios & Testing

### User Story 1 - One-Click Server Telegram Enablement (Priority: P1)

운영자는 GitHub Secrets에 저장된 Telegram bot token과 chat id를 서버 `/opt/auto-invest/.env`에 반영하고, 모바일 테스트 메시지와 일반 주문 알림 service enable까지 수동 콘솔 편집 없이 끝낼 수 있어야 한다.

**Why this priority**: 운영자가 token과 chat id를 이미 만들었는데 서버 `.env`와 systemd 명령을 직접 입력하게 하면 실수 가능성이 높고, 모바일 알림 도입 목적과 맞지 않는다.

**Independent Test**: workflow static test가 secrets 사용, SSH 경로, `.env` 갱신, test-message, service enable을 포함하고 token을 로그에 출력하지 않는지 확인한다.

**Acceptance Scenarios**:

1. **Given** `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `VULTR_SSH_*` secrets가 있을 때, **When** workflow를 수동 실행하면, **Then** 서버 `.env`에 Telegram 값이 idempotent하게 들어가고 테스트 메시지가 전송된다.
2. **Given** setup이 성공했을 때, **When** workflow가 끝나면, **Then** `auto-invest-telegram-alerts.service`가 enable 및 start 되어 일반 주문 알림 tailer가 동작한다.
3. **Given** secret이 누락되었을 때, **When** workflow가 실행되면, **Then** 어떤 secret이 빠졌는지 이름만 보고하고 값은 출력하지 않는다.

### Edge Cases

- Token, chat id, SSH private key 값은 로그에 출력하면 안 된다.
- 서버 `.env`에 기존 `TELEGRAM_*` 줄이 있으면 중복이 아니라 교체해야 한다.
- service unit이 아직 서버에 없으면 `origin/main`의 unit 파일을 읽어 설치해야 한다.
- 알림 service enable은 주문 worker를 재시작하거나 주문을 제출하면 안 된다.

## Requirements

- **FR-001**: System MUST provide a `workflow_dispatch` GitHub Actions workflow for configuring server Telegram alerts.
- **FR-002**: Workflow MUST require `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `VULTR_SSH_HOST`, `VULTR_SSH_USER`, `VULTR_SSH_PRIVATE_KEY`, and `VULTR_SSH_PORT`.
- **FR-003**: Workflow MUST mask Telegram secret values before any command can log them.
- **FR-004**: Workflow MUST update `/opt/auto-invest/.env` idempotently with `TELEGRAM_ENABLED=true`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, and `TELEGRAM_SOURCE_LABEL=auto-invest`.
- **FR-005**: Workflow MUST install or refresh `auto-invest-telegram-alerts.service` without restarting the trading worker.
- **FR-006**: Workflow MUST run `auto-invest telegram-alerts --test-message` before enabling the service.
- **FR-007**: Workflow MUST enable and start only `auto-invest-telegram-alerts.service`.
- **FR-008**: Workflow MUST NOT modify order routing, broker submission, capital, whitelist, caps, halt, or circuit breaker behavior.

## Success Criteria

- **SC-001**: Static tests prove the workflow includes secret masking, server `.env` update, test message, and service enable.
- **SC-002**: Full test suite and ruff pass.
- **SC-003**: After merge, workflow dispatch succeeds and Telegram test message is delivered.

## Assumptions

- GitHub repository secrets already contain a valid Telegram bot token and chat id.
- Existing Vultr SSH secrets can reach the server.
- Server repository exists at `/opt/auto-invest`.
