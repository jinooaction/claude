# Contract: Live Canary Gateway

## Signed order command

```text
live-canary-order <run_id> <commit> <capital> <expires_epoch> <nonce> <signature_b64>
```

서버는 형식, 만료, 공개키 서명, nonce 미사용, 배포 코드 정합, 센티넬 armed/capital/rung/NAV를
모두 확인한 뒤에만 기존 live rebalance CLI를 호출한다. 실패는 주문 호출 전 비정상 종료한다.

## Non-order evidence commands

```text
live-canary-fills
live-canary-profit <capital>
```

두 명령은 주문 제출·취소를 할 수 없다. 첫 명령은 브로커 체결을 추가-전용 장부로 동기화하고,
둘째는 기존 성과 엔진으로 live 손익을 계산해 스냅샷과 JSON을 낸다.
