# 자료 모형

ArchiveReview: status, session_count, required_sessions, missing_sessions,
missing_calendar_sessions, incomplete_archive_count, provider, synthetic,
dataset_fingerprint, decision, observation_type=HISTORICAL_RESEARCH,
live_eligible=false, orders_submitted=0.

결합 source.json의 archives에는 날짜·원본 지문·manifest 지문을 기록한다. 새 manifest는
결합5종목 CSV의 지문과 원본 공급자·합성 여부·수정 정책을 보존한다. research.json과
ledger.csv는 기존 연구기의 결과이며 review.json의 완료 표식과 구분한다.
부족 일수는 max(0,756-완결 거래일 수)다. 기간 내 누락 거래일은 달력으로 별도 계산하고
기존 연구기의 자료 품질 실패에 추가한다. 검증 불가 금액이나 정식 전진 실적을 합성하지 않는다.
