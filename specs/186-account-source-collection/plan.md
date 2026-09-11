# 구현 계획

1. 184의 AccountHistory와 모의 원본 통합 시험을 main 기반 별도 worktree에 분리한다. 거래 비용·자격·주문 코드는 포함하지 않는다.
2. main의 intraday_balance_check에 --history-db와 --execution-db만 추가한다. 기존 무옵션 출력/조회는 유지한다.
3. 기존 main 도달성 검사를 보존하는 서버 고정 경로에 비공개 저장을 연결한다. 임의 셸·PR 코드 실행을 허용하지 않는다. 저장 디렉터리 소유·권한과 실패 반환을 검증한다.
4. 관련 시험 후 전체 회귀·린트·하네스·인계·PR 관문을 수행한다. 안전 경계 변경 커밋에 this changes the safety perimeter를 기록한다.
5. 독립 출시 후 서버 원본의 수집 범위와 계산 계약을 검토해184 입력기로 이어간다. 공개 보고서에는 금액을 내보내지 않는다.

## 근거
현재 deploy/kis-smoke-on-instance.sh는 목표 커밋이 origin/main의 조상인지 검사한다. PR793 전체를 미완료 상태로 병합하는 대신 원본 수집만 독립적으로 완성한다.
