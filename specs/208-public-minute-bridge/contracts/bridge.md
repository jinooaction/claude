# 실행 계약

`scripts/public_minute_bridge.py --archive <원격 임시 입력> --assets <원격 자산 목록> --output <새 결과 폴더>`.
명령은 공급자 네트워크·브로커·주문/운영DB에 접근하지 않는다. 입력 두 월 이외는 거절한다.
복호화는 임시 폴더에만 하고 결과는추가전용 report.json이다. 원본/암호문을 다시 업로드하지 않는다.

GitHub 실행은 내부 owner·정확 PUBLIC_MINUTE_BRIDGE_SHA·검토 HEAD 일치 확인과 영구release 선점 뒤만 키에 접근한다.
실패 뒤 같은SHA 재실행은 선점 생성에서 끝난다. 취소/시간제한은 자동 재시작의 근거가 아니다.
전체 회귀 뒤 실제 분석, 원격 안전 결과 지문 확인 순서다. 208 결과 release는207 보관물과 별개다.
지연60초는 모형이다. runtime_normalization_checked는 코드 형식 검증이며 측정된 제공자/체결 동등성이 아니다.
전체181·기존 연구 실패·최소36시도/최종495세션 미개봉을 결과에서 유지한다.
