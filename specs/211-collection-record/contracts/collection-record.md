# 읽기 전용 수집 결과 계약

고정 `observe intraday-paper-status`와 `scripts/intraday_timing_status.py service-status`만 사용한다. 임의경로/쓰기/수집/서명 옵션을 추가하지 않는다.

기존 진단1.1/timing1과209영수증1.0 유지. `collection_record`는 선택적 필드이며 새 producer는 항상 정상 또는 명시 확인불가를 제공한다. 원래 영수증의 필드 부재는 그대로 허용한다.
정상 결과도 UNAUTHENTICATED이며 90초/60세션/실거래 자격을 계산하지 않는다. 서명 형식64hex는 인증 성공의 증거가 아니다.

키 추가/타입 변경/NaN/무한/시각 역전/정해진 이유 이외/다른 봉/hash/관측/4KiB초과는 거절한다. 누락/손상은 null, 기존 모의 손실제한·실주문0·정식전진0·자격거짓은 유지한다.
