# 고정 읽기 계약

`observe intraday-paper-status`의 기존3헤더와 진단JSON 유지. timing은 선택적이다.
서버 래퍼는 service-status 한 인자만 허용하며 임의 경로는 받지 않는다.
지문/버전/forward/비합성/봉/개수/관측≤게시/국소해시·이전연결 모두 일치할 때만 RECORDED.
고정 진단root/지문paper.db만 SQLite 읽기 전용/기존잠금 공유 획득으로 조회. 파일 생성 없음.
실패는 고정 UNAVAILABLE 이유이며 원래 진단 성공·실패 판정은 유지한다.
