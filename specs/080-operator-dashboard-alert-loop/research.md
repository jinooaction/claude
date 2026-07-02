# Research: 운영자 대시보드와 모바일 알림 루프

## 결정: 상태판과 알림은 같은 운영자 상태 보고서를 사용한다

**Decision**: `OperatorStatusReport`를 단일 판단 결과로 만들고, 모바일 HTML과 Telegram 알림 workflow가 이 JSON을 함께 읽는다.  
**Rationale**: 사람이 보는 화면과 알림 문구가 서로 다른 판단 로직을 가지면 상태 혼동이 생긴다. 같은 JSON을 쓰면 다음 세션도 동일한 근거를 재현할 수 있다.  
**Alternatives considered**: HTML 생성기에만 로직 추가하기. 알림 workflow가 별도 shell 조건문을 갖게 되어 drift가 커진다.

## 결정: 정상 상태는 조용히 갱신하고 개입 필요 상태만 보낸다

**Decision**: `ACTION_REQUIRED` 또는 `CRITICAL`에서만 Telegram 메시지를 전송한다. `OK`와 가벼운 `ATTENTION`은 sidecar와 상태판만 갱신한다.  
**Rationale**: 알림이 너무 많으면 운영자가 경보를 무시하게 된다. 핵심 루프 정지, 돈 경로 차단, 자율 작업 실행 불가, malformed 증거처럼 즉시 볼 가치가 있는 사건만 모바일로 보낸다.  
**Alternatives considered**: 매일 정상 요약도 보내기. 구현은 쉽지만 기존 Telegram 폭주 경험과 상충한다.

## 결정: Telegram 비밀값 부재는 실패가 아니라 건너뜀이다

**Decision**: `TELEGRAM_BOT_TOKEN` 또는 `TELEGRAM_CHAT_ID`가 없으면 workflow는 전송을 건너뛰고 `SKIPPED_MISSING_SECRETS`를 sidecar에 남긴다.  
**Rationale**: 상태판과 sidecar 발행은 Telegram 연결 여부와 독립되어야 한다. 비밀값 부재가 상태 보고 실패로 번지면 운영자가 가장 필요한 관측 표면까지 잃는다.  
**Alternatives considered**: workflow를 실패시키기. 설정 누락을 빨리 드러내지만 대시보드 갱신까지 막아 손해가 크다.

## 결정: 기존 Telegram audit tailer는 그대로 둔다

**Decision**: 주문 이벤트 알림을 담당하는 `auto-invest telegram-alerts` service는 변경하지 않는다. 새 루프는 GitHub Actions에서 자율 루프 상태만 요약한다.  
**Rationale**: 주문 audit tailer는 서버 DB와 감사 로그를 읽는 관찰자다. 이번 기능은 GitHub sidecar 기반 운영 상태 알림이다. 두 경로를 섞으면 서버 SSH, DB, 주문 이벤트와 불필요하게 결합된다.  
**Alternatives considered**: 서버 tailer에 운영 상태 알림도 넣기. 서버 의존성과 배포 영향이 커진다.

## 결정: sidecar branch를 발행하고 pipeline liveness에 비핵심으로 등록한다

**Decision**: 새 workflow는 `automation/operator-status-last-run`에 `LAST_RUN.md`와 `operator_status.json`을 발행하고, pipeline liveness는 이를 비핵심 보고 표면으로 추적한다.  
**Rationale**: 다음 세션은 알림이 실제로 실행됐는지 GitHub sidecar 하나로 확인할 수 있어야 한다. 이 루프가 멈춰도 돈 경로가 즉시 위험해지는 것은 아니므로 비핵심으로 둔다.  
**Alternatives considered**: GitHub Pages만 갱신하기. Pages는 사람이 보기 좋지만 자동화가 신선도를 추적하기 어렵다.
