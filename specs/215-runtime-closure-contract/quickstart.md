# Quickstart: 설계 반례 검토표
아래는 문서와 원래 코드의 요구 조건 대조다. 실제 서버/컨테이너/후보를 실행한 시험이 아니다.

| 번호 | 반례 | 계약이 요구하는 결과 | 후속 검사 단계 |
| --- | --- | --- | --- |
| C01 | venv 내용 동일·외부 기반Python 교체 | BASE_RUNTIME_UNAVAILABLE/불일치 | 기반 실제 파일 연결 |
| C02 | 같은 metadata 버전·설치 파일 변조 | 214 불일치 + 원래 설치 입력 대조 | 설치 연결 |
| C03 | 같은 image digest·다른 args/env | 기동 불일치 | 실제 runtime config |
| C04 | -I만 사용·허용 site의 실행 .pth | 기동안전 미평가 | site 정책/실제 module origin |
| C05 | -S로 venv prefix·의존성 경로 달라짐 | 기동·의존성 불일치 또는 미평가; ROOT/정확HEAD는 별도 확인 | 정확 Python3.11 실제 기동 |
| C06 | 깨끗한 이미지 위에 source bind mount | 격리 미평가/불일치 | actual mount/쓰기 주체 |
| C07 | 이미지 동일·native loader 외부 라이브러리 | 기반/기동 미평가 | 실제 loader/플랫폼 |
| C08 | 비교 직후 경로/이미지 교체 | CHANGED/연결 부재 | read→execute/지속 유지 |
| C09 | main 배포가 후보 root를 갱신 | CHANGED/독립성 불충족 | 합성 동시배포 |
| C10 | 전체 파일 동일·다른 code_commit | 기존 REGISTRATION_IDENTITY_CHANGED | 기존 등록 검증 유지 |
| C11 | 후보를 wheel로 옮겨 ROOT와 Git 정보 변경 | ROOT/정확HEAD 불일치 | 기존 prepare_qualification |
| C12 | 독립 입력/키/시각·수집 증명 부재 | 미평가/기존 거절, 소급 생성 금지 | 원래 입력·기존 인증 관문 |

## 이번 문서 검증
FR-001/002→C01/02/07/12, FR-003→C03~09/12, FR-004→C10/11/12,
FR-005→C06/08/09, FR-006/007→plan 후속 단계/기존 호출부,
FR-008→results/evidence 원래 영수증, FR-009→git diff 실행파일 차이0.
SC-001은 data-model 여섯 행, SC-002는 위 열두 행, SC-003은 별도 실제 보관 검증기로 확인한다.
SC-004/005는 변경 경로/계약/인계를 대조한다. 문서 반례12를 합성12통과로 보고하지 않는다.

## 후속 실제 구현 검증
별도 등급3 명세 뒤 GitHub에서 작은 합성 Git/이미지·기동·설치 입력을 사용해 C01~12를 실제 실행하고 원래 실패/성공을 남긴다.
유효 fixture는 검증기의 동작 시험이지 실제 전략·서버 등록·수집 인증 증거가 아니다.
실제 서버 지원/플랫폼이 미관측이면 해당 실제 경로는 미평가로 남긴다. macOS 시험을 Linux 증거로 대체하지 않는다.
