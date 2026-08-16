# Quickstart: Live Canary Gateway And Profit Evidence

1. 서명 gateway의 정상·변조·만료·재사용·센티넬 불일치 테스트를 실행한다.
2. live profit core에 체결 0·시세 결측·손실·양의 손익·sticky prior를 재생한다.
3. workflow와 SSH helper가 주문 권한과 관측 권한을 분리하는지 정적 검사한다.
4. 전체 테스트·린트·셸·YAML·하네스·인계 사실·PR 품질 관문을 통과한다.
5. production 환경에 개인 서명키를 저장하고 공개키만 커밋한다.
6. 머지·배포 뒤 주문 없는 live-profit workflow를 실행해 현재 체결·손익 상태를 발행한다.
7. 다음 정규장 production run에서 서명 검증·주문·체결·손익 sidecar 연쇄를 확인한다.
