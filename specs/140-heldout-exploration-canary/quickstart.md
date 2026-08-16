# Quickstart: Heldout Exploration Canary

1. `profit-evidence-probe`로 exact deployment evidence sidecar를 만든다.
2. 고정 SSH 관측명령 `observe exploration-canary`로 강화 캐너리를 실행한다.
3. `ladder-decide`에 두 JSON과 정확한 검증·라이브 설정을 전달한다.
4. 결과가 단 1이면 센티넬 PR과 배포를 확인한다.
5. 실주문은 시장시간 production 워크플로에서만 실행하고 KIS 주문·체결·잔고를 다시 읽는다.

입력이 없거나 PASS가 아니면 결과는 단 0이어야 한다.
