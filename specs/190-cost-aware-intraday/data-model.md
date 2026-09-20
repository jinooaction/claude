# 연구 기록 모델

- Contract: exact JSON 및 prior contract SHA256. 불명 필드/후보/비용 변경 거부.
- Dataset:177 manifest와 봉 계약, synthetic=false, 기간·거래일수·종목·완전성·지문.
- DevelopmentResult: 계약/코드/입력 해시,6개 양비용 지표,선택0/1개,선택 이유,장부 해시,
  생성시각 외 canonical content hash. 상태 DEVELOPMENT_REJECTED 또는 SELECTION_SEALED.
- ConfirmationResult: development content hash,확인 입력 해시,24후보 비교 기록,선택 후보의
  block/confirmation 양비용 지표,177관문별결과,장부해시. RESEARCH_REJECTED/RESEARCH_PASSED.
  입력 불능은 INVALID_EVIDENCE이며 연구 통과로 바뀔 수 없다.
- Ledger:177 JSONL 필드와 정렬. 파일 독점 생성, 중단 산출물은 완성 표시하지 않는다.

허용 전이: 개발→탈락 또는 선택고정→확인탈락/연구통과. 확인에서 개발 선택으로 되돌아가지
않는다. 어느 상태에서도 live_eligible=false이며 실주문 상태를 만들지 않는다.
