# 자료 형식
- Fixture: 새 임시 root 아래 repo, inputs. 고정 source 2파일, toy 설치2파일. 생성 당시 기대값은 별도 controller 메모리에 고정.
- Expectation: commit/tree, 경로별 SHA256·정확 mode·크기, 전체 .git inventory, 설치 계약 지문. 외부 JSON/CLI로 기대값을 주입하지 않는다.
- Observation: case, accepted/rejected, 고정 reason, Git 원래 출력 지문. 내용/경로/환경 출력 없음.
- Receipt 1.0: 정확 lab source commit, Git executable 지문, 각 case 결과, 모든 권한/이미지/인증 false. 인증된 영수증이 아닌 합성 관측이다.

