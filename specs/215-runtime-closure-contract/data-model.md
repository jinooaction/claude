# Data Model: 증거 연결의 여섯 범주
설계 계약이며 현재 소비하는 코드/JSON API는 없다. 경로·환경·키·계좌 전문을 외부 기록에 담지 않는다.

| 범주 | 고정할 입력 | 별도로 필요한 실제 관측 | 누락 결과 |
| --- | --- | --- | --- |
| 소스·의존성 원본 | 정확 commit/tree·소스117지문·원래 lock·설치 입력 지문/출처 | detached/clean 원래 저장소·기존 ROOT의 소스/독립 설치 연결 | INPUT_LINK_UNAVAILABLE |
| 설치 내용 | manifest/config/layer/platform 지문·214 파일 목록 | 실제 unpack root와 모든 내용/권한, 원래 설치 입력 연결 | INSTALLATION_UNAVAILABLE |
| 기반 실행 | Python 실행파일/base·stdlib·native/동적 로더 | 실제 사용 파일/검색 경로·플랫폼ABI·의존성 충족 | BASE_RUNTIME_UNAVAILABLE |
| 기동·경로 | 정확 args/cwd/env 허용목록·bootstrap/기동파일 | 실제 시작 config·sys.path·loaded module origin·native 로드 | STARTUP_UNAVAILABLE |
| 플랫폼·마운트 | runtime 버전/host platform·namespace/mount/hook 정책 | actual config/host·겹치는 mount/쓰기 주체/별칭 | ISOLATION_UNAVAILABLE |
| 지속 불변 | 읽기 전용 root와 독립 배포 경로·쓰기 차단 계약 | 비교→기동→진행 중 같은 세대의 변경 감지/거절 근거 | CONTINUITY_UNAVAILABLE |

## 관계 / 시각
입력 봉인 → 설치 연결 → 기동 연결 → 실행 구간의 유지 근거는 별도 단계이며 각 원래 시각과 내용 지문을 보존한다.
자료 생성 시각과 신뢰 시각을 혼동하지 않는다. self-generated 목록만으로 독립 입력을 인증하지 않는다.
code_commit은 기존 정확SHA, tree는 부가 증거다. 같은 tree/다른SHA는 자동 동등하지 않다.
원래 후보/자료/연구·사전등록/등록 시각·수집 증명/장부를 새 환경에 복사해 자동 승인하지 않는다.

## 설계의 평가 상태
NOT_ASSESSED(원래 증거 부족), MISMATCH(비교 대상 불일치), CHANGED(연결 구간 변경),
EVIDENCE_COMPLETE(명시된 증거 범주의 별도 검증 완료)를 구분하도록 후속 구현에 요구한다.
EVIDENCE_COMPLETE도 registration_verified/live_eligible/promotion_allowed가 아니다.
현재는 환경 원본이 없으므로 전체 환경 NOT_ASSESSED이며 위 상태를 판정하는 실행 코드도 없다.
213 MATCHED/214 MATCHED는 각각 기존 지역 범위에만 유효하다.
