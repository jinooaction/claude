# 명령줄 계약

`uv run python scripts/archived_event_evidence.py inspect --input <manifest.json> --output <new-report.json>`

성공은 종료0과 JSON 보고서 1개. 실패는 비0과 오류 설명이며 성공 보고서 없음. 전체 검증 후 배타적으로 새 파일을 생성한다. 기존 출력·원본은 덮어쓰지 않는다.
manifest 기준 경로의 고정된 세 파일만 읽는다. 네트워크·계좌 접근 없음. 지원하지 않는 형식·프로필·인코딩은 거부한다.
UTF-8/BOM 본문에서 script/style을 제외하고 공백 정규화해 인용 존재를 검사한다. 내용 진위·회사 연결을 자동 인증하지 않는다.
