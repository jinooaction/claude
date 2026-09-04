# 첫 체결 전 예산 갱신 계약

auto-invest ladder-decide 옵션·출력 형식 변경 없음. 기존 account-nav-json,
fundability-preview-json, live-performance-json, operational-evidence-json과
exact-main/hardening/proxy 증거를 사용한다. autoarm은 floor(NAV×0.1)의 미리보기를 읽고
CLI는 그 금액을 검증한 뒤 operational verdict로 전달한다. RESIZE만 기존 sentinel PR로 간다.
workflow_dispatch는 이 승인 절차를 실행할 수 있지만 실주문을 제출하지 않는다.
두 실제 주문 출처와 정규장·선점·주문 전 재검증은 변경하지 않는다.
