# 구현 계획

market_data/kis_history_depth.py에 독립 probe_kis_history_depth를 추가한다.
ReadTransport, get_valid_token, normalize, CALENDAR와 기존 공유 토큰 캐시를 재사용한다.
기존 live_broker 읽기 검사에 연결한다. 서버는 origin/main에 포함된 코드만 실행하는
kis-smoke 고정 통로를 그대로 사용한다. 키 이동·새 SSH 통로·배포 제한 변경 없음.
원본은 공유 토큰 캐시 부모/data 아래 kis-history-depth/run-임의식별자에 보관한다.
복구는 진단 호출 제거이며 원본은 삭제하지 않는다. 진단 실패가 기존 smoke를 실패시켜
일시적 외부 오류도 관찰 가능하게 한다. 한도/빈페이지/반복페이지는 관측 결과로 남긴다.
