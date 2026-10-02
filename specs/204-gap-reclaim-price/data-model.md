# 자료 모델

- 가설 계약: 가족/시행 수/원본 지문/28종목/개발 기간/하락 폭/시각/비용/0자본.
- 축소 입력: 원본 manifest와 고정시각 CSV 행, 압축·해제 지문과 바이트 수.
- 잠금: 성과 확인 전 입력 index와 압축 지문을 고정. 원본 지문은 사전등록과 대조.
- 종목·거래일 상태: MISSING_SIGNAL_OBSERVATION, NO_SIGNAL, MISSING_REFERENCE, REFERENCE_PAIR.
- 참조쌍: 전일/개장/신호/진입/청산, 비용별 수익. 체결 수·계좌 수익이 아님.
- 판정: REJECTED_DEVELOPMENT, INSUFFICIENT_REFERENCE_PAIRS, EXECUTION_MODEL_REQUIRED. 모든 경우 live_eligible/promotion_allowed=False.
- 원격 결과: 계약·도구·입력 지문과 모든 상태·산술 집계. 같은 입력 재계산이 전체 결과와 일치해야 함.
