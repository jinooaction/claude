# HANDOFF 084 — 운영자 대시보드와 모바일 알림 루프 (2026-07-02 KST)

main 인계 기준: `43b5da8`(PR #441). 스펙 080은 자율 성장·승격·후보 검증·돈 경로 준비도·돈 경로 정렬 루프의 sidecar를 운영자용 한 화면과 모바일 알림 판단으로 묶는 읽기 전용 운영 루프다. 운영자가 다시 물어보기 전에 "지금 돈 경로는 안전한가", "다음 자율 작업은 무엇인가", "모바일 알림이 필요한가"를 확인할 수 있게 만든다.

## 무엇이 바뀌었나

- `src/auto_invest/analytics/operator_status.py`
  - `pipeline-liveness`, `money-path`, `capital-path-readiness`, `money-gate-alignment`, `autonomous-work-execution`, `released-work` sidecar를 읽어 `OperatorStatusReport`를 만든다.
  - `OK`, `ATTENTION`, `ACTION_REQUIRED`, `CRITICAL` 상태와 `SILENT_OK`, `ATTENTION_ONLY`, `ACTION_REQUIRED`, `CRITICAL` 알림 단계를 분리한다.
  - 알림 본문에서 token, secret, chat id, 긴 숫자 조각을 마스킹한다.
- `scripts/operator_status_probe.py`
  - workflow manifest, JSON 출력, Markdown 출력, local smoke를 같은 코드 경로로 제공한다.
- `.github/workflows/operator-mobile-alerts.yml`
  - 매일 09:25 UTC와 관련 main push 때 실행된다.
  - source sidecar를 모아 `automation/operator-status-last-run`에 `LAST_RUN.md`와 `operator_status.json`을 발행한다.
  - `ACTION_REQUIRED` 이상일 때만 Telegram 전송을 best-effort로 시도한다. 비밀값이 없으면 실패하지 않고 `SKIPPED_MISSING_SECRETS`로 남긴다.
- `scripts/generate_mobile_status.py`와 `.github/workflows/mobile-status-pages.yml`
  - 기존 GitHub Pages 상태판에 운영자 요약, 실제 돈 경로, 다음 자율 작업, 돈 경로 정렬, 개입 필요 섹션을 추가한다.
- `src/auto_invest/analytics/pipeline_liveness.py`
  - `operator-status`를 비핵심 보고 sidecar로 감시한다.

## 운영상 의미

- 운영자는 GitHub Pages 상태판에서 돈 경로와 자율 작업 상태를 먼저 볼 수 있다.
- 정상 상태(`SILENT_OK`)에서는 모바일 알림을 보내지 않는다.
- 개입 필요 상태(`ACTION_REQUIRED` 또는 `CRITICAL`)에서만 Telegram 메시지를 시도한다.
- 알림 전송 실패나 비밀값 부재는 주문·자본·live 설정 경로에 영향을 주지 않고 sidecar에만 남는다.
- 기존 Telegram audit-log tailer는 주문 이벤트 관찰자이고, 새 operator-status workflow는 운영 상태 요약자다. 두 경로는 역할이 다르다.

## 배포 후 실제 실행 증거

- PR #441 merge commit: `43b5da8f99e0b28db9049a2023d0b618647b0f73`
- `Deploy on merge to main` run `28561843637`: success, commit `43b5da8`
- `Operator mobile alerts` run `28561843669`: success, commit `43b5da8`
- `Pipeline liveness watchdog` run `28561843616`: success, commit `43b5da8`
- 최신 `automation/operator-status-last-run:LAST_RUN.md`
  - `overall_status=OK`
  - `alert_level=SILENT_OK`
  - `send_status=NOT_ATTEMPTED`
  - `money-path=PREVIEW_ONLY`
  - `capital-path-readiness=ACCUMULATING_EDGE`
  - `money-gate-alignment=ALIGNED_WAITING`
  - `autonomous-work-execution=EXECUTION_READY`
  - 다음 자율 작업 후보: `candidate-e481b0309206`
  - 제목: `레짐·성과 분석을 후보 점수화 입력으로 승격`

## 후속 보정

#441 main push의 `Mobile status page (GitHub Pages)` run `28561843601`은 failure였다. 원인은 상태판 workflow가 의존성 설치 없이 bare `python3`로 `scripts/generate_mobile_status.py --manifest`를 실행하는데, 새 `operator_status.py`가 `auto_invest.notifications.telegram`을 import하면서 `httpx`가 없는 환경에서 실패한 것이다.

후속 브랜치 `Codex/080-operator-dashboard-alert-loop-followup`은 `operator_status.py`가 Telegram transport 모듈을 import하지 않게 고친다. 알림 문구 마스킹과 길이 제한은 분석 모듈 내부의 표준 라이브러리 코드로 처리하고, 실제 Telegram 전송 모듈은 workflow의 전송 단계에서만 사용한다.

## 안전 경계

- 위험 등급: 2(운영 자동화와 상태판/알림 보정)
- 실제 주문 실행: 없음
- 브로커 실주문 API 호출: 없음
- 자본 증액, 자본 배분, 허용 종목 확대, 포지션 한도 완화, live 전략 교체, live sentinel 변경: 없음
- 헌법, 커널 목록, 주문 제한, 감사 로그 schema, 비밀값 저장, 외부 유료 서비스 변경: 없음
- workflow는 기존 automation sidecar와 GitHub Actions Secrets만 읽고, 자기 sidecar 또는 GitHub Pages만 갱신한다.
- Telegram token/chat id는 Secrets에서만 읽고, 로그·HTML·sidecar에는 원문을 남기지 않도록 마스킹한다.
- 배포 성공은 dry-run worker 코드 반영이다. 실거래 전환이나 실제 주문을 의미하지 않는다.

## 검증

PR #441 머지 전:

- `uv run pytest tests/unit/test_operator_status.py tests/integration/test_operator_status_probe.py tests/integration/test_mobile_status_page.py tests/unit/test_operator_mobile_alerts_workflow.py tests/unit/test_pipeline_liveness.py` -> 38 passed
- `uv run ruff check` 관련 파일 -> All checks passed
- `uv run python scripts/operator_status_probe.py --manifest` -> OK
- 로컬 sample JSON/Markdown/HTML smoke -> OK
- workflow YAML Ruby parse -> OK
- `uv run pytest` -> 2414 passed, 4 skipped
- `uv run ruff check src tests` -> All checks passed
- `uv run python scripts/agent_harness_probe.py --strict` -> OK (14/14)
- `uv run python scripts/check_handoff_facts.py` -> OK
- PR 품질 관문 -> OK

후속 보정 브랜치:

- `PYTHONPATH=src python3 scripts/generate_mobile_status.py --sidecar-dir /tmp/unused --manifest` -> OK
- `uv run pytest tests/unit/test_operator_status.py tests/integration/test_mobile_status_page.py tests/unit/test_operator_mobile_alerts_workflow.py` -> 13 passed
- `uv run ruff check src/auto_invest/analytics/operator_status.py tests/unit/test_operator_status.py tests/integration/test_mobile_status_page.py tests/unit/test_operator_mobile_alerts_workflow.py` -> All checks passed
- `uv run pytest` 첫 재실행은 stale `HANDOFF.md` 때문에 `test_agent_harness_probe.py` 2건만 실패했다. 이 handoff 갱신이 `마지막 main 커밋` 행을 #441 기준으로 고쳐 그 원인을 제거한다.

## 다음 세션 한 줄

스펙 080은 `operator-status` sidecar와 모바일 상태판을 추가해 자율 루프의 돈 경로, 다음 작업, 개입 필요 상태를 운영자가 바로 볼 수 있게 했다. #441에서 operator-status와 deploy는 성공했고, 모바일 상태판 publish 실패는 후속 브랜치에서 Telegram transport import 의존을 끊어 복구 중이다.
