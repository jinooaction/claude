# 스펙 080: 운영자 대시보드와 모바일 알림 루프

**기능 브랜치**: `Codex/operator-dashboard-alert-loop`  
**작성일**: 2026-07-02  
**상태**: Draft  
**위험 등급**: 등급 2(운영 자동화와 모바일 관측 표면 변경)

## 사용자 시나리오 및 테스트

### 사용자 이야기 1 - 모바일에서 전체 자율 루프 상태를 한눈에 본다 (우선순위: P1)

운영자는 Codex에게 다시 묻지 않아도, 모바일 상태판에서 자율 성장 루프, 돈 경로, 다음 작업 후보, 완료 후보 장부, 생존 감시 상태를 한 화면에서 확인할 수 있어야 한다.

**독립 테스트**: 최신 sidecar 스냅샷 디렉터리로 상태판을 생성하면 전체 상태, 실제 돈 경로, 다음 자율 작업, 개입 필요 항목이 HTML과 JSON에 함께 표시된다.

**인수 시나리오**:

1. **Given** `pipeline-liveness`, `money-path`, `capital-path-readiness`, `autonomous-work-execution`, `released-work`, `money-gate-alignment` sidecar가 있다.
2. **When** 모바일 상태판 생성 루프가 실행된다.
3. **Then** 운영자는 모바일 화면에서 종합 상태, 실제 돈 상태, 다음 자율 작업, 알림 필요 여부, 증거 링크를 볼 수 있다.

### 사용자 이야기 2 - 개입이 필요한 사건만 모바일 알림으로 받는다 (우선순위: P1)

운영자는 매일 모든 정상 로그를 읽는 대신, 핵심 루프 정지, 돈 경로 차단, 자율 작업 실행 불가, 완료 장부 이상처럼 개입이 필요한 사건만 모바일 알림으로 받아야 한다.

**독립 테스트**: 입력 sidecar가 `CRITICAL`, `BLOCKED`, `OPERATOR_APPROVAL_REQUIRED`, malformed 중 하나를 포함하면 알림 판정은 `ACTION_REQUIRED` 이상이 되고, 정상 입력에서는 `SILENT_OK`가 된다.

**인수 시나리오**:

1. **Given** 핵심 sidecar가 오래됐거나 돈 경로 정렬 루프가 `BLOCKED`를 발행한다.
2. **When** 모바일 알림 루프가 실행된다.
3. **Then** 운영자에게 보낼 짧은 한글 알림 본문과 상태판 링크가 생성된다.
4. **And** Telegram 비밀값이 없으면 알림 전송은 건너뛰고 sidecar에는 `send_status=SKIPPED_MISSING_SECRETS`가 기록된다.

### 사용자 이야기 3 - 알림 루프 자체도 감시와 인계에 남는다 (우선순위: P2)

운영자와 다음 세션은 모바일 알림 루프가 언제 실행됐고, 무엇을 보냈거나 건너뛰었는지 재현할 수 있어야 한다.

**독립 테스트**: 알림 루프는 `LAST_RUN.md`와 `operator_status.json`을 발행하고, pipeline liveness 기본 감시 목록에 비핵심 sidecar로 등록된다.

**인수 시나리오**:

1. **Given** 알림 루프 workflow가 실행된다.
2. **When** 실행이 끝난다.
3. **Then** `automation/operator-status-last-run`에 최신 요약, 전송 결과, 안전 경계, 결정 JSON이 남는다.
4. **And** pipeline liveness는 `operator-status` sidecar 신선도를 비핵심 보고 표면으로 추적한다.

### 예외 상황

- 입력 sidecar 일부가 없거나 malformed이면 해당 표면만 `missing` 또는 `malformed`로 표시하고, 다른 표면으로 가능한 요약을 만든다.
- Telegram 비밀값이 없거나 전송에 실패해도 주문, 자본, live 설정, 기존 sidecar 발행을 막지 않는다.
- 정상 상태에서는 매일 조용히 sidecar와 대시보드만 갱신하고 불필요한 모바일 알림을 보내지 않는다.
- 알림 본문과 JSON에는 토큰, 계좌번호, app key, app secret, chat id 원문이 남으면 안 된다.

## 요구사항

### 기능 요구사항

- **FR-001**: 시스템은 주요 자율 루프 sidecar를 읽어 운영자용 단일 상태 보고서를 생성해야 한다.
- **FR-002**: 보고서는 전체 상태를 `OK`, `ATTENTION`, `ACTION_REQUIRED`, `CRITICAL` 중 하나로 분류해야 한다.
- **FR-003**: 보고서는 실제 돈 경로 상태, 자본 준비도, 돈 경로 정렬 상태, 다음 자율 작업, 완료 후보 장부, pipeline liveness 상태를 포함해야 한다.
- **FR-004**: 모바일 상태판은 운영자용 상태 보고서 JSON을 포함하고, 모바일 화면에서 전체 상태와 개입 필요 항목을 먼저 보여야 한다.
- **FR-005**: 알림 루프는 `ACTION_REQUIRED` 또는 `CRITICAL`일 때만 모바일 메시지를 보내야 한다.
- **FR-006**: 알림 루프는 Telegram 비밀값이 없으면 실패하지 않고 전송을 건너뛴 사실을 sidecar에 기록해야 한다.
- **FR-007**: 알림 루프는 `LAST_RUN.md`와 `operator_status.json`을 `automation/operator-status-last-run` sidecar로 발행해야 한다.
- **FR-008**: pipeline liveness는 `operator-status` sidecar를 비핵심 보고 표면으로 감시해야 한다.
- **FR-009**: 알림 본문과 sidecar는 비밀값과 계좌 식별자를 마스킹해야 한다.
- **FR-010**: 시스템은 주문, 자본 배분, broker 호출, live 설정 변경, 허용 종목·포지션 한도 변경, 서버 SSH 명령, 외부 유료 서비스 호출을 수행하지 않아야 한다.
- **FR-011**: workflow는 주요 루프가 끝난 뒤 실행되도록 예약되고, 관련 코드가 `main`에 들어오면 1회 자가검증 실행되어야 한다.
- **FR-012**: 상태 보고서는 같은 입력과 같은 기준 시각에서 같은 JSON을 만들어야 한다.

### 핵심 엔티티

- **OperatorStatusReport**: 실행 메타데이터, 전체 상태, 알림 판정, 표면별 상태, 다음 행동, 안전 불변조건을 담는 운영자 요약.
- **OperatorSurface**: 한 sidecar 입력의 존재 여부, 파싱 상태, 요약 상태, 운영자 메시지, 원천 참조를 담는 단위.
- **MobileAlertDecision**: 알림 등급, 전송 필요 여부, 전송 본문, 전송 결과를 담는 판정.
- **DashboardSection**: 모바일 상태판에서 먼저 보여야 할 실제 돈 상태, 자율 성장 상태, 다음 작업, 개입 필요 항목을 담는 표시 묶음.

## 안전 경계

- 읽기 전용이다. 기존 automation sidecar와 현재 GitHub 실행 메타데이터만 읽고 자기 sidecar와 정적 HTML만 발행한다.
- 실거래, 주문, 계좌 자본 배분, 라이브 전략 변경, 허용 종목·포지션 한도 변경, 감사 로그 schema 변경을 하지 않는다.
- Telegram은 관찰 채널이다. Telegram 실패는 주문 경로, 자본 게이트, sidecar 판정에 영향을 주지 않는다.
- 비밀값은 repository, PR 본문, handoff, sidecar, HTML, 로그에 원문으로 남지 않아야 한다.

## 성공 기준

- **SC-001**: 정상 sidecar 입력에서는 상태판이 `OK` 또는 `ATTENTION`을 표시하고 모바일 알림 판정은 `SILENT_OK`가 된다.
- **SC-002**: 핵심 sidecar `CRITICAL` 또는 돈 경로 `BLOCKED` 입력에서는 알림 판정이 `ACTION_REQUIRED` 이상이 된다.
- **SC-003**: Telegram 비밀값이 없는 workflow 실행은 실패하지 않고 `SKIPPED_MISSING_SECRETS`를 기록한다.
- **SC-004**: 생성된 HTML은 모바일 폭에서도 전체 상태, 실제 돈 상태, 다음 작업, 개입 필요 항목 텍스트가 겹치지 않는 구조를 가진다.
- **SC-005**: `operator_status.json`은 같은 입력과 같은 기준 시각에서 결정론적으로 동일한 핵심 필드를 낸다.
- **SC-006**: `uv run pytest`와 `uv run ruff check src tests`가 통과한다.
- **SC-007**: 새 workflow에는 broker 주문, live 전환, 서버 SSH, `git push origin main`, 외부 비용 명령이 포함되지 않는다.

## 가정

- 운영자는 GitHub Pages 상태판을 모바일에서 열 수 있다.
- Telegram bot token과 chat id는 이미 GitHub Secrets에 있거나 없을 수 있다. 없으면 알림 전송을 건너뛰는 것이 정상 동작이다.
- 상태 보고의 1차 입력은 이미 발행된 automation sidecar다. 새 루프는 투자 판단을 새로 계산하지 않는다.
- 알림은 주문 체결 실시간 알림이 아니라 자율 루프 운영 상태 알림이다. 기존 `auto-invest telegram-alerts` audit tailer와 역할이 다르다.

## 비목표

- 실제 매매, 실거래 전환, 자본 배분, 전략 교체를 수행하지 않는다.
- 새로운 유료 알림 서비스나 별도 모바일 앱을 도입하지 않는다.
- Telegram 서버 tailer service를 재구성하거나 trading worker를 재시작하지 않는다.
- 기존 pipeline liveness의 핵심/비핵심 판정 의미를 바꾸지 않는다.
