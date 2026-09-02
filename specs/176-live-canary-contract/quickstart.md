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
   첫 후보 뒤에도 거래일 선점이 없으면 root 소유 `auto-invest-live-canary.timer`가 10:35 이후
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

## 5. 독립 scheduler 검증

```bash
uv run pytest tests/unit/test_live_canary_server_scheduler.py \
  tests/unit/test_live_canary_gateway.py \
  tests/unit/test_live_canary_workflow.py \
  tests/unit/test_sync_units.py
```

고정 저장소 시험에서 배포 `HEAD` 뒤 `HANDOFF.md`만 추가된 현재 main은 통과해야 한다. 같은 위치에
`src/`, `deploy/`, `.github/workflows/`, 설정 또는 분류되지 않은 파일을 추가하거나 계보를
분기시키면 scheduler와 내부 `systemd-order`가 모두 선점·broker write 전에 실패해야 한다.
서버 실행 요약 1.1은 `code_commit`과 `deployed_code_commit`을 함께 표시해야 한다.

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
