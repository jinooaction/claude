# 검증 순서

1. 신규 identity 반례로 기존 네 누락의 실패를 확인한다.
2. 목록과 경로/내용 지문 구현 후 identity/selection/qualification 검사를 실행한다.
3. 삭제·읽기 실패·변경 중·문서 변경·기존 지문 자격을 검사한다.
4. 외부 접속 없는 사용자self-test의 실제주문0/live_eligible=false를 확인한다.
5. 전체pytest/ruff·하네스·인계·PR 품질 검사와 배포를 확인한다.

권한을 발급하거나 자동 변경하지 않는다. 전체 단타 전략 관문은 별도로 유지한다.
