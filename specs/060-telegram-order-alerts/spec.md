# Feature Specification: Telegram Order Alerts

**Feature Branch**: `Codex/telegram-order-alerts`  
**Created**: 2026-06-22  
**Status**: Draft  
**Input**: User description: "텔레그램 봇으로 모바일에서 micro GTAA 검증과 일반 주문 실행·매수·매도·거부·체결 결과를 실시간으로 알고 싶다. 무료인지 확인하고 구현한다."

## User Scenarios & Testing

### User Story 1 - Receive Micro GTAA Run Alerts on Mobile (Priority: P1)

운영자는 micro GTAA 자동 실행이 시작되어 preflight, 손실 브레이커, live 주문 단계에서 어떤 결론을 냈는지 모바일 텔레그램으로 바로 확인할 수 있어야 한다.

**Why this priority**: 다음 정규장 자동 실행은 KIS 원인 확정의 첫 관측 기회다. 운영자가 GitHub Actions 화면을 계속 새로고침하지 않아도 preflight 차단, 주문 거부, 접수 여부를 알 수 있어야 한다.

**Independent Test**: 텔레그램 비밀값이 없는 워크플로는 조용히 skip하고, 비밀값이 있는 모의 실행은 run URL과 preflight/live 요약을 포함한 메시지를 구성하는지 확인한다.

**Acceptance Scenarios**:

1. **Given** 텔레그램 비밀값이 설정되어 있고 micro GTAA 워크플로가 끝났을 때, **When** 결과 발행 단계가 실행되면, **Then** run id, event, preflight reason, live outcome, 주문 요약, run URL을 포함한 텔레그램 메시지가 전송된다.
2. **Given** 텔레그램 비밀값이 없을 때, **When** micro GTAA 워크플로가 끝나면, **Then** 알림 단계는 skip되고 workflow 결론을 실패로 바꾸지 않는다.
3. **Given** 텔레그램 API가 일시 실패할 때, **When** 알림 전송이 실패하면, **Then** workflow의 주문·측정·sidecar 결과는 그대로 유지되고 알림 실패만 로그에 남는다.
4. **Given** micro GTAA live 결과에 거부된 매수 또는 매도 주문이 있을 때, **When** 결과 발행 단계가 실행되면, **Then** 현재가 기준으로 "정상 체결됐다면 지금 더 유리했는지"를 양수/음수 기회손익으로 계산해 sidecar와 텔레그램에 함께 표시한다.

---

### User Story 2 - Receive General Live Order Event Alerts (Priority: P2)

운영자는 서버에서 돌아가는 일반 live worker가 주문 의도, 주문 접수, 게이트 거부, 브로커 거부, 체결, halt, 오류를 감사 로그에 남길 때 모바일 텔레그램으로 요약을 받을 수 있어야 한다.

**Why this priority**: GitHub Actions 기반 micro GTAA뿐 아니라 일반 live worker의 매수·매도·체결 결과도 실시간으로 알아야 돈 경로를 운영할 수 있다.

**Independent Test**: SQLite audit_log에 주문 이벤트를 넣고 알림 tailer를 dry-run으로 실행하면, 각 이벤트가 민감정보 없이 사람이 읽을 수 있는 메시지로 변환되고 마지막 처리 seq가 저장되는지 확인한다.

**Acceptance Scenarios**:

1. **Given** `ORDER_INTENT`와 `ORDER_SUBMITTED`가 audit_log에 추가되었을 때, **When** 알림 tailer가 새 seq를 읽으면, **Then** 종목·방향·수량·주문번호 요약을 텔레그램으로 보낸다.
2. **Given** `ORDER_REJECTED_BY_BROKER`가 diagnostics와 함께 추가되었을 때, **When** 알림 tailer가 새 seq를 읽으면, **Then** 마스킹된 KIS 코드·메시지·HTTP 상태를 포함하고 계좌번호·토큰·앱 키는 포함하지 않는다.
3. **Given** `FILL`이 추가되었을 때, **When** 알림 tailer가 새 seq를 읽으면, **Then** 체결 수량·가격·시각 요약을 보낸다.
4. **Given** tailer가 재시작되었을 때, **When** state file에 마지막 seq가 있으면, **Then** 이미 보낸 이벤트를 중복 전송하지 않는다.

---

### User Story 3 - Enable Alerts Without Widening the Trading Safety Perimeter (Priority: P3)

운영자는 텔레그램 비밀값을 안전하게 넣고, 알림 장애가 주문·체결·브레이커·halt 판단을 바꾸지 않는다는 것을 확인할 수 있어야 한다.

**Why this priority**: 알림은 관찰 도구일 뿐 돈 경로의 의사결정자가 되면 안 된다. 외부 API 장애가 주문 경로를 막거나 비밀값을 노출하면 안전 경계가 깨진다.

**Independent Test**: 텔레그램 전송 실패를 주입해도 tailer가 bounded retry 후 다음 poll로 넘어가고, 주문 라우터와 worker 코드 경로는 변경되지 않는지 확인한다.

**Acceptance Scenarios**:

1. **Given** `TELEGRAM_BOT_TOKEN`과 `TELEGRAM_CHAT_ID`가 없을 때, **When** 알림 기능이 실행되면, **Then** 주문 경로와 worker 시작은 실패하지 않고 알림만 비활성으로 보고된다.
2. **Given** 텔레그램 토큰이 잘못되었을 때, **When** 전송이 실패하면, **Then** 주문 경로는 영향을 받지 않고 tailer 로그만 실패를 기록한다.
3. **Given** 운영자가 알림을 켜고 끄고 싶을 때, **When** systemd service를 enable/disable하면, **Then** 주문 worker는 재시작하지 않아도 된다.

### Edge Cases

- 텔레그램 메시지는 4096자 제한보다 짧게 잘라야 한다.
- 응답 diagnostics에 계좌번호, token, app key, app secret, authorization 값이 들어오면 반드시 마스킹되어야 한다.
- 텔레그램 API 장애는 bounded retry 후 포기하고 다음 이벤트 처리를 계속해야 한다.
- 첫 실행에서 오래된 audit_log 전체를 폭주 전송하지 않아야 한다. 명시적 replay 옵션이 없으면 현재 마지막 seq부터 시작한다.
- state file이 이미 있지만 오래된 seq를 가리키는 경우에도 기본값으로 최신 소량만 catch-up하고 오래된 backlog 전체를 폭주 전송하지 않아야 한다.
- 동일한 `ERROR` 이벤트가 반복 기록되면 지정된 cooldown 안에서는 같은 오류를 중복 전송하지 않고 cursor는 계속 전진해야 한다.
- GitHub Actions micro 알림은 secrets가 없거나 비어 있으면 skip해야 한다.
- 알림은 실주문, 취소, 체결 동기화, halt 설정을 직접 수행하면 안 된다.
- 거부 주문 기회손익 현재가 조회가 실패해도 주문, sidecar 발행, 텔레그램 전송은 실패하면 안 되며, 조회 실패 사유와 현재가 누락 종목을 메시지에 드러내야 한다.

## Requirements

### Functional Requirements

- **FR-001**: System MUST support Telegram Bot API notifications for micro GTAA workflow results when `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` are configured.
- **FR-002**: System MUST skip Telegram notification attempts without failing the workflow when Telegram secrets are absent.
- **FR-003**: System MUST provide an audit-log tailer that reads new rows after a persisted last seq and formats live order events for Telegram.
- **FR-004**: The audit-log tailer MUST default to starting at the current maximum seq when no state file exists, unless an explicit replay option is supplied.
- **FR-005**: System MUST notify at least these event types: `ORDER_INTENT`, `ORDER_SUBMITTED`, `ORDER_REJECTED_BY_GATE`, `ORDER_REJECTED_BY_BROKER`, `FILL`, `CANCEL`, `CIRCUIT_BREAKER_TRIPPED`, `HALT_SET`, and `ERROR`.
- **FR-006**: System MUST mask tokens, app keys, app secrets, authorization values, and account identifiers before sending any Telegram message.
- **FR-007**: Telegram send failures MUST NOT block, alter, retry, cancel, or submit any order.
- **FR-008**: Telegram delivery MUST use bounded timeout and bounded retry; no unbounded loop is allowed inside a single send attempt.
- **FR-009**: System MUST expose a dry-run mode that prints would-send messages without requiring a Telegram token.
- **FR-010**: System MUST provide operator setup documentation for creating a Telegram bot, finding chat id, setting GitHub secrets, and setting server `.env` values.
- **FR-011**: System MUST include automated tests for message formatting, secret masking, state advancement, dry-run behavior, and absent-secret skip behavior.
- **FR-012**: System MUST NOT change strategy, capital, whitelist, order caps, circuit breaker thresholds, broker order submission behavior, or existing audit event semantics.
- **FR-013**: The audit-log tailer MUST cap stale-cursor catch-up by default and expose an operator option to adjust or disable that cap.
- **FR-014**: The audit-log tailer MUST suppress repeated identical `ERROR` alerts within a bounded cooldown while still advancing the persisted cursor.
- **FR-015**: System MUST evaluate rejected rebalance BUY/SELL orders against current marks when available and report opportunity PnL where positive means the rejected order would currently be more favorable.
- **FR-016**: Telegram messages for micro GTAA and audit-log order alerts MUST use readable sections that separate status, order result, diagnostics, opportunity PnL, and next verification context.

### Key Entities

- **Telegram Alert Config**: Bot token, chat id, enabled flag, timeout, retry count, and source label loaded from environment or `.env`.
- **Audit Alert Cursor**: Persisted last processed audit seq that prevents duplicate messages.
- **Order Alert Event**: Sanitized view of an audit_log row and payload suitable for mobile display.
- **Micro Workflow Alert**: GitHub Actions summary for one micro GTAA run with preflight, live outcome, and run URL.
- **Rejected Order Opportunity Report**: Read-only report derived from rebalance JSON and current marks that quantifies hypothetical PnL for rejected orders without retrying them.

## Success Criteria

### Measurable Outcomes

- **SC-001**: With Telegram secrets absent, the micro GTAA workflow notification step exits successfully without sending.
- **SC-002**: With a mock Telegram API, one `ORDER_REJECTED_BY_BROKER` row produces exactly one alert containing KIS diagnostic fields and no unmasked account or token values.
- **SC-003**: Restarting the audit tailer with an existing state file sends zero duplicate alerts for already processed seq values.
- **SC-004**: Dry-run mode can be run locally with no Telegram token and prints the same alert text that would be sent.
- **SC-005**: The implementation passes targeted tests, full `uv run pytest`, and `uv run ruff check src tests`.
- **SC-006**: Operator documentation lets a mobile user validate Telegram delivery with a test message before enabling the audit tailer service.
- **SC-007**: A stale cursor pointing far behind the audit log sends only the configured newest catch-up count and advances to the newest processed seq.
- **SC-008**: Repeated identical `ERROR` rows inside the cooldown window produce one mobile alert, not one alert per row.
- **SC-009**: A rebalance result with rejected BUY and SELL orders produces deterministic opportunity PnL in JSON/text, and missing current marks are reported without failing the workflow.

## Assumptions

- Telegram Bot API can be used free of charge for this notification use case, subject to Telegram's published API policies and rate limits.
- The operator will create the bot and provide `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`; these secrets are never committed.
- The first implementation sends text-only alerts, not inline buttons or rich media.
- GitHub Actions notifications and server audit-log tailing are separate channels because GitHub workflow results and continuous worker order events originate in different places.
- The audit-log tailer is an observer process. It is not a new trading decision point.
