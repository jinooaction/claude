# 내부 계약

`execution_fingerprint(candidate, provider)`의 호출부와 반환 자료형 및 지원 공급자 검사는 유지한다. 버전2 소스 경로·내용을 결합하며 성공 반환은 후보 승인이나 실행 권한이 아니다.
`source_identity()`는 고정 목록을 검증해 정렬된path/sha256 항목을 반환한다. 사용자 경로·계좌·네트워크 입력 없음. 실패는ValueError로 기존 자격 검사에서 거부된다.
새 CLI·원격 주문 경로·설정 파일 없음. `intraday_operator.py self-test`는 외부 접속 없이 통과해야 한다.
