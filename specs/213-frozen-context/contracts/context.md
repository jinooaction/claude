# 명령 계약

`python scripts/intraday_frozen_context.py --expected <미서명비교선언> --candidate <후보루트> --main <갱신루트>`

현재 실행기의 prefix/모듈/설치 메타데이터를 직접 조회한다. 다른 Python을 실행하거나 환경을 설치하는 옵션은 없다.
MATCHED는 exit0, MISMATCH/UNAVAILABLE는 exit2. 형식오류도 제한된 JSON이며 원문 exception/환경/경로를 출력하지 않는다.
일치해도 program_readiness=NOT_ASSESSED, declaration_authenticated=false, dependency_files_verified=false,
continuous_immutability_verified=false, registration_verified=false, live_eligible=false,promotion_allowed=false,orders_submitted=0이다.
기존 모의/실주문/등록 경로가 이 결과를 소비하지 않는다. 비교 입력의 지문은 재현용이며 서명이 아니다.
module name은 최상위 이름만, source relative_path는후보src 내부, 내용 지문은선언과맞아야 한다.
의존성은현재환경metadata버전/위치만비교하며파일전체를봉인했다는주장없음이다.
