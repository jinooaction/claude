# 조사와 결정

- main3782909에서 order_router.py/authority.py/risk/gates.py/market_data/intraday.py의 메모리상 바이트 변경에도 실행 지문이 같았다. 대조군intraday_budget.py는 달랐다. 실제 승인 우회는 입증하지 않았다.
- 근거: `/Users/mason/Projects/claude-data-research/20260921-hf-raw/execution-identity-audit-20260928/`의 source-change-probe-v1.json 및 direct-import-audit-v1.json. 기존38개 지문 파일의 직접 절대 import 중21개가 빠져 있었다.
- runtime_identity는 장부·중지 경로·위험 설정·보유 기준을 묶으며 소스 누락을 대체하지 않는다. ExecutionQualification.__call__은 매번 execution_fingerprint를 비교한다.
- 결정: 기존38개를 보존하고 절대·상대 로컬 import 및 package 초기화를 따라 검토한117개 경로 후보를 고정한다. 경로와 내용을 함께 결합하고 목록 구현도 지문에 묶는다.
- 네 파일만 추가하면 취소·인증·공통 자료형 누락을 남긴다. 전체 소스 트리는 무관한 보관자료 연구도60세션 관찰을 무효화한다. 런타임 자동 import/실행은 하지 않는다.
- 범위는 로컬 파일 일관성이다. 실행 메모리·동적 적재·외부 패키지·운영 환경·체결 동등성 전체 인증이 아니다. 기존 지문의 불일치 거부를 유지하며 승인 발급·실주문·자본 배정 없음.
