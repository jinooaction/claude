# 연구 결정

근거: 기존 registration/qualification은 실제 로드된 모듈 경로의 Git HEAD로 재계산한다.
212 재검증 생성시각 보정과 정확 코드 유지 문제는 별개다. 이전22 합성 검사는 동일 트리의 다른 커밋 거절을 확인했다.

- 선택: 독립 지역 비교 도구부터 구현. main/후보의 경로 구분·detached HEAD·clean 상태·lock·실행 prefix·모듈 위치·설치 버전 정보를 비교한다.
- 이유: 폴더 이름만 고정해도 모듈/가상환경이 main에서 로드되면 분리되지 않는다. 설치 없는 합성 반례로 먼저 확인할 수 있다.
- 제외: 문서SHA 예외/자동 재등록/전진 시계 초기화/기존 진단에 attest 자동 적용/main 배포 중단/키 생성.
- 한계: 미서명 선언/의존성 파일 전체/ignored 파일 전체/계속되는 변조/악성 실행기 자체는 인증하지 않는다.
  일치 결과에도 declaration_authenticated=false/dependency_files_verified=false/continuous_immutability_verified=false를 남긴다.
- 운영: 모듈 위치는 import를 실행하지 않는 PathFinder로 조회한다. Git은 fetch/checkout/reset 없이 읽기 명령만, 환경의 GIT_* 주입을 이어받지 않는다.
  fsmonitor 보조 실행을 끄는 일회성 읽기 옵션만 사용하고 저장소 설정/훅을 수정하지 않는다.
- 불명확한 정책 없음. 실제 설치/운영 활성화는 이번 기능의 후속이며 이 도구의 성공만으로 진행하지 않는다.
