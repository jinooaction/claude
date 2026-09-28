# 실행 소스 연결 검증 기록

기준 main: `37829096639c7ef60c3df43bf899fce516667fc4`. 검증일: 2026-09-28.
현재 상태: 구현 및 관련/전체 회귀 검사 통과, PR855/main454877a 병합. 서버 배포는 장중 제한으로 대기 중이다.

## 확인한 변화

기존 버전에서 공통 주문·권한·위험·시세 파일의 변경을 검출하지 못하는 네 반례를 먼저 재현했다. 새 버전은 해당 변경을 검출한다. 실제 자격 검사에서도 이미 발급된 지문의 공통 권한 코드가 바뀌면 `QUALIFICATION_STRATEGY_CHANGED`를 반환한다. 실제 권한 파일을 발급하거나 변경하지 않았다.

기준 커밋 함수의 소스 목록 할당식을 AST로 추출하여 비교한 결과 기존38개 모두 새117개 목록에 포함됐다(누락0개). 로컬 정적 import와 package 초기화의 누락 검사, 서로 다른 체크아웃의 지문 재현, 문서 비영향, 삭제·디렉터리·심볼릭/하드 링크·읽기 오류·검사 중 파일 변경·목록 중복 거부가 통과했다.

## 현재 완료한 검사

- 관련 검사: `uv run pytest tests/unit/test_intraday_identity.py tests/unit/test_intraday_selection.py tests/unit/test_intraday_qualification.py tests/unit/test_intraday_registration.py -q` — **114 passed in 4.41s**.
- 전체 린트: `uv run ruff check src tests` — 통과.
- 실제 CLI 자체 시험: `uv run python scripts/intraday_operator.py self-test` — 부분 체결/취소, 영구 중지/재시작 통과. 오프라인 실행, 실제 주문0건, 실거래 적격 false.
- 하네스: `uv run python scripts/agent_harness_probe.py --strict` — **14/14 통과**.
- 인계 사실 검사: `uv run python scripts/check_handoff_facts.py` — 통과. main의 인계 전 코드 기준 `dda232f`와 일치.
- 전체 검사: `uv run pytest -q` — **5005 passed, 13 skipped in 893.46s**, 종료 코드0. `/tmp/197-full-pytest.log` 보존. 12개는 명시적인 실 KIS 검사 조건이 꺼져 있어, 1개는 이미 가동된 사다리의 가동 전 전용 검사라 건너뛰었다. 실 KIS 검증 통과를 뜻하지 않는다. 실행48628은 종료했으므로 다시 대기하거나 재시작하지 않는다.

## 계산 비용

이 Mac의 동일 체크아웃에서 `source_identity()`를 연속100회 실행: 평균 **18.478ms**, 95백분위 **22.583ms**, 최대 **29.415ms**. 읽기 캐시가 데워진 로컬 파일 측정이며 서버의 최악 지연을 보장하지 않는다. 매 호출에서 내용을 읽고 검사 전후 및 전체 읽기 후 파일 상태를 비교한다. 외부 API나 계좌 호출은 없다.

## 유지되는 한계

버전2는 과거 지문과 의도적으로 다르다. 기존 승인·관측을 자동 이전하지 않는다. 외부 패키지·동적 적재·실행 메모리까지 인증하는 기능이 아니다. 한도·허용 종목·감사·배포 제한·60세션 관찰은 그대로다. 전체181의 T013~T016(통과 전략, 전진 관찰, 실거래 단계 검증과 생산 증거)은 미완료다.

## 병합과 배포 시도

- 구현 커밋 `968b38723486d444cd3d3e98105d12fbb14eefc3`, 문서 보완 후 PR855 최종 head `55f8a0bae946280a8c670f397066ca577cc03f79`. 두 커밋 사이에는 명세 문서만 변경했다.
- 병합 `454877a149128be1dd8c96b3fc6b6507becaca50`, 2026-09-28T13:30:27Z. PR 품질 검사 통과와 병합 가능 상태를 확인하고 merge 방식으로 병합했다.
- 배포 실행36429103946은 종료 success. 그러나 현재 시도의 서버 로그는13:30:53Z에 `deploy refused: US market is open (NYSE session in progress). Next allowed deploy: 2026-09-28T20:00:00Z.`를 기록했다. `START_EXIT=1`, 긴급 배포 false였다. 워크플로 성공은 연기 처리 성공이며 서버의 새 코드 실행 증거가 아니다.
- 다음 확인: 한국9월29일05시 이후 기존 타이머의 배포 기록에서 대상 커밋과 `DEPLOY_COMPLETED`를 확인한다. 아직 해당 배포 상관키나 완료 감사 증거는 없다. 과거 감사 기록을 새 배포 증거로 재사용하지 않는다.
- T009는 이 서버 확인이 끝날 때까지 미완료로 남긴다. 주문·자본·권한 발급 없음.
