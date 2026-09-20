# 자료 모델

후보: family=`shock_recovery`, timeframe15/30, variant=`anchor|session`,
parameters=`shock_bps:124,headroom_bps:82,stop_bps:82,exit_at_anchor:0|1`.
지문은191 계약 지문을 포함한다. 기존177/190 지문은 불변이다.

개발 증거: schema/family/stage/contract/code/dataset,1645sessions,
4후보의 기준·가혹 성과, 탈락 이유, 선택 후보 또는null, 장부 해시/행 수,
내용 해시, `holdout_read:false`, 기존 연구 안전 필드.
상태는 `DEVELOPMENT_REJECTED` 또는 `CONFIRMATION_REQUIRED`, 둘 다 실거래 불가.

장부는177 형식. 매수 시도는 미체결도 하루 자격을 소비한다.
잔량 청산을 계속 시도하고 최종 미청산은 누락하지 않는다.
재계산 검증은 원본부터 결과/장부를 비교하여 해시만 다시 만든 변조도 거부한다.
