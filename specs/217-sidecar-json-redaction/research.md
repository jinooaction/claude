# Research
## Decision
기존 구조화 JSON 가림을 유효한 JSON 코드 블록에 재사용한다.
## Rationale
실제 edge-autoarm 원본 `2ed1d9bd1bc87b2d8dce2141947f355d0e699f65`의
evidence_age_hours가 소수 일부 가림으로 JSON 파싱 불능이다.
발행 workflow는 decision.json을 LAST_RUN.md의 JSON fence에 복사한 뒤 공통 스크립트를 호출한다.
.json/.jsonl에는 이미 구조 기반 보호가 있지만 .md와 stdin에는 regex만 적용한다.
## Alternatives
정규식 숫자 범위 완화는 일반 문장의 계좌 번호 보호를 약화해 제외.
소비자의 손상 JSON 허용은 증거 합성 위험으로 제외.
옛 소수 추측 복원, 자본 사다리 수동 재실행도 제외.
유효하지 않은 블록은 기존 텍스트 가림을 유지한다. 발행 workflow의 기존 실패 무시 정책은 이번 수정에서 확대하지 않는다.
## Dependency and policy
새 라이브러리/외부 호출/미확인 기술 선택 없음. 기존 sensitive key와 후보 식별자 계약을 따른다.
계좌 NAV는 원래 보호 의도에 맞춰 account_nav_usd/AccountNavUsd 정규화 별칭으로 가린다.
