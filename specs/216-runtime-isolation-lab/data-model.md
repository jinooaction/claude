# Data Model
- LabInput: 고정 기반 reference/platform, script SHA, 생성 fixture 파일별 SHA. 공급망 독립 인증이 아니다.
- CreatedContainer: 정확 ID/image ID/created 상태/Path/Args/Config/HostConfig/Mounts. 시작 전 자료형 포함 비교.
- CaseResult: 고정 case ID·예상 상태·안전 출력. 성공/예상 부정 관측 구분.
- LabReport: schema1/scope SYNTHETIC_RUNTIME_LAB/source SHA/지문/cases/미평가 false/orders0.
- ActualReceipt: 원래215 감사·두 정기 진단·원격 digest·captured 검증. 실험 보고서와 별개.
상태: GUARD→BUILD→CREATED→VALIDATED→STARTED→OBSERVED→CLEANED. 실패는 종료/성공 report0.
부정 case는 CREATED→REJECTED→REMOVED, start0.
