# Data Model: 별도로 연결해야 할 원래 증거

이번은 문서 형식 계약이다. 아래 자료를 발급/인증하는 실행 코드나 실제 레코드를 만들지 않는다.

| 자료 | 필수 연결 | 별도 미평가 |
|---|---|---|
| review_input | schema/scope·검토 코드/전체 tree·허용 전체 경로/모드/크기/SHA·입력 출처·검토주체/원래시각 | 선언 자체의 인증 방법 |
| repository_evidence | 원래 commit 객체·전체 tree/blob·후보 ROOT 내부 Git 디렉터리·정확 HEAD·detached/clean·원래 전체 파일 바이트 | 저장소 역사 전범위의 비밀/진위 |
| execution_sources | 기존 source_identity의 원래 결과/개별 바이트 지문·모듈 ROOT | 기존 지문에 없는 소스/의존성 |
| installation_inputs | lock 원래바이트/SHA·직접/전이 버전·wheel/sdist/빌드도구 바이트·출처·대상 Python/ABI/platform | 공급망 진위·기반 환경 |
| installation_result | 입력별 실제 설치 파일/전체 SHA·권한·설치기 버전·명령·무네트워크 결과·원래 종료 | RECORD 자체보고 밖의 진위 |
| image_link | 기반 manifest/platform·빌드 imageID·위 입력 묶음 지문·실제 내부 관측·containerID/config | hostkernel/mount교체/관리자변경/지속불변 |

문서상 식별자는 모두 별도 필드이며 Git OID와 SHA256를 혼용하지 않는다.
현재 저장소 SHA1 commit40자리와 SHA256 바이트 지문64자리를 구분한다.
schema/scope·타입·키 집합은 후속 구현에서 폐쇄형으로 검증한다. 중복키·추가키·잘못된 null은 거절한다.
검토 기대값은 이미지 자체 보고로부터 만들어 비교하지 않는다. 원래 입력과 실행 출력의 출처를 분리한다.

## 상태
DESIGN_ONLY → 후속 별도 구현의 SYNTHETIC_INPUT_LINK_ONLY 또는 LINK_REJECTED/INPUT_UNAVAILABLE.
실제 관측이 없는 값은 null/미평가이며 추정 보충하지 않는다.
어느 상태도 REGISTRATION_VERIFIED/실행 허가로 전환되지 않는다.
declaration_authenticated/actual_candidate_environment_installed/runtime_closure_verified/
continuous_immutability_verified/registration_verified/live_eligible/promotion_allowed는 모두 false,
program_readiness=NOT_ASSESSED, orders_submitted=0을 유지한다.
