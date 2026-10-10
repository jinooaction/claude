# 자료 구조

## Archive input identity v1

schema=1, scope=intraday-archive-input-v1, provider, synthetic, adjustment_policy,
archives=[session/raw_sha256/manifest_sha256]. 기존 정렬된 원래lineage를 사용하며 날짜/원본manifest와source 전체 지문이 포함된다.
파생 결과의 dataset_fingerprint는 이 구조의 정규표현 SHA다. 원래 파생manifest/source/CSV는 실제생성시각으로 보존된다.

## Research content identity v1

schema=1, scope=intraday-research-content-v1, report=원래 결과에서 generated_at_utc만 제외한 모든필드.
원본 input identity·비용/평가/판정/후보/거래지문·preregistrationSHA·code_commit과 알 수 없는 필드는 유지한다.
숫자 비정상값은 거절한다. 서명/계좌/키는 이 자료 구조에 없다.

## 등록 상태

기존 ResearchSelection 형식/등록 envelope/HMAC/서버시간/정확 코드/권한 검증은 유지한다.
이전 digest 방식 또는 변경내용은 REGISTRATION_IDENTITY_CHANGED 등 기존 오류로 거절한다.
새 방식으로 재서명/소급등록/부재 보충을 수행하지 않는다.
