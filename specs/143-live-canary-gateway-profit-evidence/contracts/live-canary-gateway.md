# Contract: Live Canary Gateway

## Signed order command

```text
live-canary-order <run_id> <commit> <capital> <expires_epoch> <nonce> <signature_b64>
```

서버는 형식, 만료, 공개키 서명, nonce 미사용, 배포 코드 정합, 센티넬 armed/capital/rung/NAV를
모두 확인한 뒤에만 기존 live rebalance CLI를 호출한다. 실패는 주문 호출 전 비정상 종료한다.

## Signed no-order preflight command

```text
live-canary-verify-order <run_id> <commit> <capital> <expires_epoch> <nonce> <signature_b64>
```

수동 실행은 이 명령만 사용한다. 주문 명령과 같은 production 승인·서명·권위 검사를 수행하되
live rebalance CLI는 호출하지 않으므로 주문은 항상 0건이다. 실제 주문 명령은 평일 예약 실행만 쓴다.

## Non-order evidence commands

```text
live-canary-fills
live-canary-fills <start_yyyymmdd> <end_yyyymmdd>
live-canary-profit <capital>
```

두 명령은 주문 제출·취소를 할 수 없다. 첫 명령은 브로커 체결을 추가-전용 장부로 동기화한다.
날짜 범위를 주면 과거 KIS 체결을 멱등 복구하며, 브로커가 확인한 수량·가격·시각만 기록한다.
둘째는 검증된 시스템 가동 전 보유 수량·평단을 시작 상태로 사용해 기존 성과 엔진으로 live
손익을 계산하고 스냅샷과 JSON을 낸다. 시작 상태는 체결 행을 만들거나 주문 원장을 바꾸지 않는다.
