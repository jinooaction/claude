# 실행 절차

명령 구현과 표적 시험을 마쳤다. 실제 재생은 계약·코드 커밋 뒤 실행한다.
전체 테스트·가격 재생은 Mac 자원을 점유하지 않는 원격 실행 위치를 먼저 확인한다.

원격 CI는 `research-fixtures/198/README.md`에 출처를 표시한 고정 개발 묶음을
`scripts/unpack_late_session_input.py --output-dir <새입력폴더>`로 검증·복원한다.
다섯 종목의 2013-08-23~2020-03-06 자료만 있으며 계좌·최종 확인 자료는 없다.

```sh
uv run python scripts/late_session_probe.py develop --bars-dir <개발자료폴더> --manifest <고정manifest> --output-dir <새결과폴더>
uv run python scripts/late_session_probe.py verify --bars-dir <동일개발자료폴더> --manifest <동일manifest> --evidence <결과폴더>
```

새 출력 폴더만 허용한다. verify는 원자료로 재계산하며 파일을 고치지 않는다.
다른 manifest는 가격을 읽기 전에 거부한다. confirm·계좌·주문 명령은 없다.
탈락도 정상적인 연구 결과다. CLI 성공은 전략 통과와 다르며 개발 통과도 실거래
적격이 아니다. 181의 후속 요구사항을 생략하지 않는다.
