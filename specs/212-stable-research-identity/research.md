# 설계 판단

## 확인한 문제

고정3a03ac5d의 작은 합성1세션/390행을 같은 코드에서1초 간격으로 재검증했다.
원본7파일/코드는 같고 두번 모두 INSUFFICIENT_EVIDENCE인데 dataset_fingerprint와 research_digest가 달랐다.
원래 probe는 claude-data-research/20261011-211-actual-collection/probe-research-identity.py와 JSON이다.
review_archives는 now가 들어간 파생manifest를 dataset 지문으로 사용하고, select_research는 generated_at이 포함된 전체 report bytes를 해시한다.
등록은 그 지문과 정확한 code_commit을 묶으므로 재검증이 등록과 달라질 수 있다. 실제 통과전략/실서버 등록을 검증한 결과가 아니다.

## 결정

- 자료 지문은 기존 검증이 읽은 원본 lineage 전체(raw/manifestSHA·날짜)와 출처/합성/조정을 묶는다. 원본manifest의 수집시각과 CSV지문도 이 안에 포함된다.
- 파생 결합 원본의 실제 생성 시각은 그대로 둔다. 파생 시간으로 원본 수집시각을 덮거나 고정된 가짜 now를 주지 않는다.
- 연구 지문은 새 버전 문맥과 정규화된 전체보고서에서 generated_at_utc 한 필드만 제외한다. 다른 필드/알 수 없는 필드는 계속 묶인다.
- 원래 report에 입력 지문 문맥을 남겨 다음 세션이 같은 지문을 재현하게 한다.
- 코드 SHA 변경 거절은 보존한다. 문서만 바뀌어도 등록이 달라지는 정책은 별도 문제이며 이번에 완화하지 않는다.

## 검토한 대안

- 기존 보고서/합격 파일을 그대로 신뢰: 독립 재계산을 잃으므로 거절.
- 매번 새 서명/등록: 최초 등록시각·60세션을 깨므로 거절.
- report 생성시각을 원본시각으로 가짜 고정: 실제 생성 원본 보존을 깨므로 거절.
- 이름/제공자 변경으로 원래 합격 연결: 종목/시세/체결 동등성을 잃으므로 거절.

새 지문 방식이 이전 등록과 안 맞으면 원래 거절을 보존한다. 입력/판정/서명·키 변경 검증은 줄이지 않는다.
