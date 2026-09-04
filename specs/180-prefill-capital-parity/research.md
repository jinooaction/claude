# 결정 근거

## 관측

33925261456 no-order preflight는142에서 ENTRY_BLOCKED였다. IAUM45/SCHX30.4552,
target0.166666/0.333334, invested_fraction0.99, IAUM1/SCHX2에서
L1=0.2508478873, max_leg=0.1519020685. 기존25%/15% 경계는 정상 차단했다.
sentinel은Aug31 NAV1427.63에 따른142, 현재 smoke33925193723 NAV1434.91의10% 내림은143이다.
autoarm은143을 검증하지만 ladder는 RESIZE_DRIFT_PCT10 미만을 STAY해 주문예산142와 어긋난다.

## 선택

현재10%의 모든 진입 검증과 명확한 전략0체결이 있는 operational rung1만 작은 차이를
RESIZE한다. 수익 최적화가 아닌 검증·실행 정합이다. CLI는 이미
expected_operational_capital_usd와 검증된 current-NAV preview를 전달한다.

## 대안과 반례

- 임계값 완화·143 수동 쓰기·비율 상향: 거부. 기존 승인 경로를 우회한다.
- floor 수량: IAUM0도16.4999%p 오차라15%를 넘는다.
- 모든 단계 drift 제거: 체결 후 불필요한 예산·측정 변경을 만든다.
- 가격 상승으로143도 불가능하면 계속 차단한다. 다음 장의 실제 접수·체결은 별도 검증한다.
