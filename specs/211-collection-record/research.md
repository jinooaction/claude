# 설계 판단

기준 실제main e15a841ef04a66e02b8064f02807feb269aac8a4. 기존210 운영 기록 병합 뒤 코드 변화0.

- 결정: 첫 처리 event의 선택적 collection_proof만 읽는다. 근거: PaperRuntime.process가 동일 봉 재처리를 생략하므로 최신 batch/hash/mtime는 최초 처리의 증거가 아니다. 대안: 외부 batch 검색은 다중 재수집과 retrieved_at 호출 의미 차이 때문에 배제했다.
- 결정: 서명 구조·자료 지문·시각만 검증하고 authentication_verified=false를 유지한다. 근거: collect_attested_kis/verify_collection은 이미 있지만 키 접근/검증 권한은 이번 범위가 아니다. 대안: 키를 읽거나 HMAC을 새로 만드는 중복 경로는 배제했다.
- 결정:210 검증기를 재사용한다. 근거: 공유잠금/국소행/조회시간/메모리 한도가 이미 있다. 대안: 두 별도 장부 조회는 일관성과 비용을 악화시켜 배제했다.
- 결정: 같은 진단의 선택적 collection_record로 노출한다. 근거: 현재 service_cycle은 attestation을 사용하지 않는다. 실제 PROOF_ABSENT를 표시할 수 있지만 이를 정식전진 실패 또는 기능 미구현으로 확대하지 않는다.
- 결정: provider게시/개별API수신/처리완료를 계속 미평가로 둔다. 자료 반환 뒤 기록은 전체 호출의 반환 시점이고 retrieved_at 필드는 producer마다 의미가 다르다.

미해결 설계 질문 없음. 제공자/라이선스/조정/체결동등성/전략 합격은 기존 별도 미확인으로 유지한다. 가격성과/495개봉/원본취득 없음.
