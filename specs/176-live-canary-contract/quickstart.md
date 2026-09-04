# 빠른 실행: 증거 수렴형 실거래 검증 캐너리

## 1. 좁은 계약 검사

```bash
uv run pytest tests/unit/test_operational_canary_evidence.py \
  tests/unit/test_fundability.py \
  tests/unit/test_capital_ladder.py \
  tests/unit/test_live_entry_revalidation.py
```

운영 증거가 참이어도 `alpha_confirmed=false`, `capital_fraction=0.10`, `max_rung=1`이어야 한다.
생산 run `33540003731` 고정 입력에서는 SCHX만 정수 주 표현 가능 목표로 분류되고 IAUM은 전체
오차 계산에 남아야 한다. 표현 가능 목표가 0개이거나 표현 가능한 목표가 미자금이면 실패해야 한다.

## 2. 전체 로컬 검사

```bash
uv run pytest
uv run ruff check src tests
uv run python scripts/agent_harness_probe.py --strict
uv run python scripts/check_handoff_facts.py
```

## 3. 생산 증거 확인

main 배포 뒤 profit-evidence sidecar의 `operational_canary_evidence.json`과 strategy-factory
sidecar의 `capital_entry_evidence.json`을 각각 내려받는다. 역할, 코드 커밋, 생성 시각, 후보 ID,
전략 지문을 독립 검사한다. 진단용 `strategy_factory.json`으로 대체하지 않는다.

## 4. 실제 주문 순서

1. 미국 정규장 밖에서 main 배포와 sidecar 갱신을 끝낸다.
2. 자본 사다리가 단 0에서 `entry_route=operational_canary` 단 1로 바뀌었는지 확인한다.
3. 최신 NAV 10%와 정수 주 주문 미리보기가 한도를 넘지 않는지 확인한다.
4. 뉴욕 현지 10:17부터 13:53까지 최대 12분 간격의 비정각 GitHub 예약을 주 경로로 사용한다.
   첫 후보 뒤에도 거래일 선점이 없으면 root 소유 `auto-invest-live-canary.timer`가 10:35~15:35에
   독립 fallback을 깨운다. 두 출처는 같은 production 거래일 선점 장부를 사용해 첫 실행만 주문
   경로로 보내며 후속 실행은 중복으로 종료한다.
5. 실제 시작이 지연됐으면 실주문 CLI의 XNYS 검사에서 차단되고 다음 개장 시각이 기록되는지
   확인한다. 이 경우 주문을 강제로 재실행하지 않는다.
6. 시작 뒤 장이 마감됐으면 각 실제 주문 직전 검사에서 남은 주문이 차단되고, 워크플로 단계가
   성공으로 오인하지 않고 종료 코드 75를 표시하는지 확인한다.
7. 주문 접수, KIS 체결 조회, 전략 장부, 계좌 정합, 감사 sidecar를 같은 실행 ID로 맞춘다.
8. 체결이 없으면 완료하지 않고 다음 정규장 실행을 계속 관찰한다.
9. 중복 예약은 최초 run ID와 `source`를 보고한다. 최초 출처가 server timer면 고정
   `live-canary-scheduled-status` 결과를 뒤늦은 production sidecar가 같은 ID로 발행하는지 확인한다.
10. GitHub 예약이 늦으면 `Live canary server timer status (read-only)` 워크플로를 수동 실행한다.
    성공 sidecar `automation/live-canary-server-status-last-run`의 `observation_status=ok`와
    `server_scheduled_status.json`을 확인한다. 이 조회는 서버 timer나 주문을 시작하지 않는다.
11. 성공 요약이 없으면 같은 sidecar의 `server_runtime_status.json`에서 마지막·다음 timer 발화,
    service 결과·종료값과 원문 없는 고정 사건 코드를 확인한다. 이 파일이 있어도 관측 workflow는 실패가 정상이며,
    실제 주문 성공으로 해석하지 않는다. 임의 journal 조회나 service 수동 시작으로 재현하지 않는다.
12. 성공 요약이 있지만 `orders_submitted=0`이면 같은 sidecar의
    `server_order_diagnostics.json`에서 해당 run ID의 계획 건수와 정화된 결과 상태·gate를 확인한다.
    이 파일에는 가격·현금·계좌·원문 reason이 없어야 하며, 이를 근거로 거래일 선점을 수동 삭제하거나
    서비스를 다시 시작하지 않는다. 원인을 고친 뒤에는 별도 안전 계약이 허용하는 다음 자동 후보로만
    검증한다.
13. 결과가 `REJECTED_BY_BROKER`면 진단 1.1의 `broker_rejections`에서 KIS 코드, HTTP 상태,
    예외 종류, TR ID, 주문 거래소와 주문 구분을 확인한다. `msg1`, 응답 원문, 가격·계좌·주문번호가
    없음을 확인하고, 실제 코드 의미와 요청 형식을 확인하기 전에는 같은 주문을 재시도하지 않는다.
14. KIS 주문 프로토콜 보정은 캡처 시험에서 `custtype=P`, `tr_cont=""`와 기존
    `TTTT1002U`·지정가 본문이 함께 나가는지 확인한다. 배포 뒤 KIS smoke와 주문 없는 preflight로
    조회·첫 진입을 확인하되, 실주문은 수동으로 만들지 않는다. 다음 자동 정규장 실행에서 브로커
    접수·체결·전략 감사·계좌 대사가 모두 연결될 때만 해결로 판정한다.
15. 같은 날 복구가 필요하면 기존 거래일 선점을 삭제하지 않는다. 먼저 server timer 최초 요약이
    `orders_submitted=0`, 모든 계획 결과가 명시적 브로커 거부, 체결 동기화·측정·정합 정상,
    열린 주문 0건인지 확인하고 정확한 사고 manifest와 보정 커밋을 코드 리뷰·배포한다.
16. 다음 root timer가 자동 발화해 별도 복구 장부를 한 번 소비했는지 확인한다. service를 수동
    시작하거나 GitHub 수동 이벤트로 실주문하지 않는다. 복구 실패 뒤에는 그날 세 번째 시도를
    만들지 않는다.
17. 진단에 `EGW00201`이 있으면 live rebalancer가 burst 없는 `5회/초, capacity=1` 제한기를
    사용하는지 시험하고, 주문 호출의 `retry_transient=False`가 유지되는지 확인한다. 고친 뒤에도
    최초 선점을 지우거나 주문을 수동 재전송하지 않고 exact 사고 manifest가 허용한 다음 자동
    server timer 한 번으로만 검증한다.

## 5. 독립 scheduler 검증

```bash
uv run pytest tests/unit/test_live_canary_server_scheduler.py \
  tests/unit/test_live_canary_gateway.py \
  tests/unit/test_live_canary_workflow.py \
  tests/unit/test_live_canary_server_status_workflow.py \
  tests/unit/test_sync_units.py
```

고정 저장소 시험에서 배포 `HEAD` 뒤 `HANDOFF.md`만 추가된 현재 main은 통과해야 한다. 같은 위치에
`src/`, `deploy/`, `.github/workflows/`, 설정 또는 분류되지 않은 파일을 추가하거나 계보를
분기시키면 scheduler와 내부 `systemd-order`가 모두 선점·broker write 전에 실패해야 한다.
서버 실행 요약 1.1은 `code_commit`과 `deployed_code_commit`을 함께 표시해야 한다.
복구 시험은 원래 `order-sessions.tsv` 행이 바뀌지 않고 별도 retry 장부만 한 줄 추가되며,
접수 불명·부분체결·열린 주문·manifest 불일치·기소비 슬롯에서 추가 CLI 호출이 0건인지 확인한다.

배포 뒤 `systemctl list-timers auto-invest-live-canary.timer`가 active이고 다음 시각이 뉴욕 현지
10:35 이후인지 확인한다. `live-canary-scheduled-status [14자리 run_id]`는 고정된 최신 또는 지정
요약만 읽어야 하며,
`systemd-order`는 SSH forced-command에서 거부되어야 한다.

## 6. 즉시 복구

문제가 생기면 센티넬을 `armed:false`, 단 0, 자본 0으로 내리고
`auto-invest-live-canary.timer`를 disable한다. 기존 주문·체결·감사 행은 삭제하지 않는다.
이미 산 전략 보유분은 기존 위험 축소 주문 경로로만 정리한다.

## 7. 배포 감사 장부 확인

main 배포 뒤 수동 `Deploy audit log verification` 워크플로를 실행한다. 이 워크플로는 SSH 경계의
고정 `deploy-audit` 명령만 호출하며 서버에 셸 본문을 보내지 않는다. 성공 sidecar에서
`ssh_exit=0`, `audit_status=ok`, `terminal_event=DEPLOY_COMPLETED`를 확인한다. 선택적 correlation
ID는 8~64자리 16진수만 허용되고, 잘못된 값은 서버 데이터베이스를 읽기 전에 차단되어야 한다.
