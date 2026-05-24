# Contract — CLI 표면 변경

새 최상위 명령은 최소화한다. 판단 지점은 거래 루프/리포트에 통합되며, 관측은 기존 명령을 확장한다.

## `auto-invest report --date <d>` (확장, FR-022)
- 기존 일일 리포트 출력에 **판단 요약 섹션** 추가: 그날 `daily_summary` 판단 지점의 narrative + alerts. LLM 실패 시 "요약 생성 불가(결정론적 카운터만)".

## `auto-invest efficiency` (확장, FR-040)
- 기존 비용/효율 분해에 **판단 지점별(decision_class별)** 행 추가: 총비용·평균지연·호출 수·**폴백 발생률**·예산 대비 사용률.
- 합산 보존: 판단 지점 비용 합 ≤ token_usage 총계와 정합(SC-006).

## (선택) `auto-invest judgment status` — 신설 검토
- 판단 지점 레지스트리 상태(각 지점 활성/예산소진/캐너리단계)를 한 화면 JSON으로. tasks 단계에서 필요성 판단(없어도 efficiency/report로 충족 가능 → 우선순위 낮음).

## 거래 루프 (CLI 아님, 런타임 통합)
- `auto-invest run`/워커 루프가 트리거 발화 시 판단 지점을 호출하고 자문을 order_router에서 소비. 새 CLI 플래그 없이 룰 파일이 판단 지점 활성/소비 규칙을 선언.
- 룰 TOML 확장: 판단 지점 소비 규칙(`halt_min_confidence`·`size_down_factor`·`block_min_confidence`)을 룰/액션에 선언적으로 부착(`config/rules.py` 비커널 확장).
