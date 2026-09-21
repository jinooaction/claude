# Data model

입력 schema_version=1, issuers(고정 CIK 목록), documents, events. 빈 사건 허용.
문서: id/path/sha256/url/source_claims. source_claims는 게시·수정·SEC 접수 원문 주장 문자열 목록.
사건: id/event_key/issuer_cik/kind/report_period_end/event_date/time_label/document_id/
evidence_quotes/supersedes/symbol/lineage_status. kind=scheduled|reported,
time_label=date_only|before_open|after_close|unspecified. 기간 미기재는 null.
id는 버전 식별자, event_key는 같은 회사·같은 종류 사건의 안정적인 묶음 식별자다.
종목 연결 상태 verified|unverified는 검토자의 주장으로 보존한다. 자동 입증하지 않는다.

import 원문별 observed_start/observed_end와 모든 사건 확인 완료 verified_at을 기록한다.
query 이용 가능 시각은 max(observed_end, verified_at). UTC 정규화, 시간대 필수.
supersedes는 같은 회사·event_key·kind의 기존 버전만 가리키며 시간 역전/분기를 거부한다.
정정본과 후속 import의 확인 시각은 이전 기록보다 엄격히 뒤여야 한다. 동률도 거부한다.
직렬화한 최종 manifest 역시 10MiB 이하여야 하며 초과 시 출력 폴더 생성 전에 거부한다.
원문 게시일과 사건 날짜는 조회 자격 계산에 사용하지 않는다.
현재 파일 지문은 파일 동일성만 증명한다. 로컬 관측 기록은 외부 시각 공증이 아니다.

조회는 관측된 최신 버전만 반환하고, 아직 없는 회사는 coverage_unknown_issuers로 표시한다.
각 버전의 의미와 인용문은 검토 필요 상태이며 observation_available을 전략 적격으로 바꾸지 않는다.
