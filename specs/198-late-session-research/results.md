# 구현 검사 기록

2026-09-28. 사전등록 계약 `f77301e` 이후 구현했다. 계약 바이트는 변경하지 않았다.
이 기록은 실자료 성과 보고가 아니다. 최초 구현 검사에서는 가격 자료를 열지 않았다.
이후 아래 원격 전달 단계에서는 고정 개발 CSV를 검사·포장했다. 최종 확인 구간은 열지 않았다.

## 표적 검증

```sh
nice -n 10 uv run pytest tests/unit/test_late_session_intraday.py tests/integration/test_late_session_cli.py tests/unit/test_noise_band_intraday.py tests/unit/test_intraday_paper_challenger.py -q
nice -n 10 uv run ruff check src tests scripts/late_session_probe.py
nice -n 10 uv run python scripts/agent_harness_probe.py --strict
nice -n 10 uv run python scripts/check_handoff_facts.py
```

66 passed / 2.02초, 린트 통과, 하네스 14/14, HANDOFF 사실 검증 통과.
최초 구현 전 시험은 새 모듈 부재로 실패했고 구현 후 통과했다.
이후 사용하지 않는 import와 줄 길이 지적을 수정했다.

정상장·반일장·일광 절약 시간·휴일 직전 거래일·동일가·관측 누락·미래 가격 불변,
5분 변환 보존·기존 18개 후보 보존, 비용·미체결 시도·부분 청산·잔여 수량,
다른 manifest 사전 거부·덮어쓰기 거부·원자료 재계산·재봉인한 가짜 지표 거부,
기록된 코드와 재계산 코드 차이 거부를 검사했다.

## 남은 검증

원격 전체 pytest는 새 연구 CI로 실행한다. 실제 개발 1,645일 재생·재계산은 아직
실행하지 않았다. 연구 실행 위치와 입력 자료 범위를 확인해야 한다.
후보 수익성, 독립 확인, 181 전진 관찰·실제 체결 증거는 미완료다.
전체 목표를 완료 처리하지 않는다. 실주문·자금 배정·화면 조작은 없었다.

## 개발 입력의 원격 전달 보완

공급자의 2022년 이전 자료 CC BY 4.0 범위와 출처 조건을 실제 페이지에서 확인했다.
`research-fixtures/198/README.md`에 출처·가공 내역·한계를 표시했다.
다섯 CSV의 기존 지문·7개 열·개발 날짜 범위·각 127,734행을 확인하고 gzip으로 포장했다.
총 압축 크기 10,534,652바이트. 계좌·로그인 정보 및 최종 확인 기간은 포함하지 않는다.
원본 manifest SHA-256은 `c4b6c6336ee0747464fde730f6d894ba3b8814c14567406f49cb0e528ea8fdfc`로 동일하다.

복원 도구는 모든 파일의 크기·지문을 검사한 뒤에만 새 출력 폴더를 만든다.
새 입력·명령·신호 관련 시험 31개가 1.68초에 통과했다. 전체 src/tests와 두 CLI의
ruff, workflow YAML 구문, 하네스 14/14 및 HANDOFF 검사를 확인했다.
실제 개발 재생과 재계산은 새 원격 development 작업에서 수행하고 장부를 보존한다.
이 입력 연결 보완으로 코드가 바뀌었으므로 최신 커밋으로 전체 회귀도 재실행한다.
