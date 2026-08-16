# HANDOFF-147 - Lot-Aware Execution Proxy

## 결론

#620으로 소액 단 1 자본이 실제 주문을 만들 수 있는 경로를 `main`에 출시했고, 배포 뒤 KIS
실계좌 미리보기에서 `SPYM` 1주와 `GLDM` 1주가 계획되는 것까지 확인했다. 다만 2026-08-16은
일요일이어서 실주문 작업은 실행하지 않았다. 실제 주문·체결·수익은 아직 0이며 목표는 완료가 아니다.

## 현재 사실

- main: `2be2d3d` (#620), 기능 커밋 `7643040`
- deploy run: `31919928105`, success
- KIS smoke run: `31919928101`, success
- KIS 미리보기 run: `31919969616`, preview success 뒤 실주문 작업 취소
- 센티넬: `armed:true`, rung 1, `capital_usd:293`, 실계좌 NAV 1466.83달러
- 매수가능현금: 934.27달러
- 필요 현금: 180.10달러
- 계획 매수금액: 178.32달러
- 계획 매도금액: 0달러
- 계획 주문: `SPYM` BUY 1주, 지정가 91.57달러
- 계획 주문: `GLDM` BUY 1주, 지정가 86.75달러
- 비관리 보유: `ORANY` 28주 SELL 요청은 `unmanaged_holding`으로 보류
- 실제 주문·체결·수익: 0

## 구현 의미

검증된 신호 자산은 `SPY/IEF/GLD` 그대로이며 전략 지문도 바뀌지 않았다. 체결 계층만
`SPY→SPYM`, `IEF→IEF`, `GLD→GLDM`으로 명시적으로 매핑한다. 소액 자본에서는 opt-in
`nearest` 정수 주 반올림을 쓰되 총 계획 금액이 투자 가능 자본을 넘으면 목표 오차가 가장 적게
늘어나는 주식부터 제거한다.

미리보기와 실주문 명령은 모두 `--account-wide`를 사용해 KIS 실제 보유와 구매 가능 현금을
원본으로 삼는다. 매핑 누락·중복·허용 목록 불일치는 실패 폐쇄한다. 허용 매수 종목은
`SPYM/IEF/GLDM`뿐이며 `ORANY`는 자동 매도하지 않는다.

## 검증 증거

- focused: 51 passed
- 전체: 2827 passed, 6 skipped
- `uv run ruff check src tests`: pass
- `git diff --check`: pass
- `uv run python scripts/check_handoff_facts.py`: OK
- `uv run python scripts/agent_harness_probe.py --strict`: OK, 14/14
- PR 품질 관문: pass

## 다음 정규장 관문

1. 예약 `0 15 * * 1-5`의 다음 미국 정규장 실행을 확인한다.
2. GitHub production 환경 승인이 대기하면 운영자가 승인한다. 이 경계는 우회하지 않는다.
3. 최신 live-canary sidecar와 KIS 주문 조회에서 `SPYM/GLDM` 실제 접수·체결을 대조한다.
4. 잔고, 구매 가능 현금, 주문 감사 로그를 확인하고 `ORANY` 매도가 없음을 확인한다.
5. 위 증거가 모두 맞을 때만 T012를 완료한다. 실제 수익은 별도 계좌 손익 증거로 확인한다.

## 중단과 되돌림

주문 종목·수량이 미리보기와 다르거나, 비관리 보유 매도가 생기거나, 캡·손실 예산·정규장
검사가 실패하면 주문을 진행하지 않는다. 긴급 중단은 센티넬을 `armed:false`로 내려 후속 실주문을
차단한다. 코드 되돌림이 필요하면 #620의 merge commit `2be2d3d`를 새 PR에서 revert하되,
감사 로그와 기존 계좌 기록은 삭제하지 않는다.
