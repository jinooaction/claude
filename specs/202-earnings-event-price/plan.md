# Implementation Plan: 실적 공시 뒤 가격 반응 진단

**Branch**: `codex/202-earnings-event-price` | **Date**: 2026-10-02 | **Spec**: [spec.md](spec.md)

## Technical context

Python 3.11, 기존 XNYS 거래소 달력, 표준 CSV/JSON. 오프라인 읽기 전용 입력과
새 출력 JSON 하나. 30개 파일을 한 번씩 순차 읽고 메모리에는 사건 날짜만 보존한다.
저우선순위 단일 작업으로 실행하여 맥북 사용을 방해하지 않는다.

## Constitution check

I/II: 허용 종목·포지션 한도를 바꾸지 않는다. III: 실행 중 LLM 호출 없음.
IV/V: 감사 로그와 비밀값 접근 없음. VI/X: `Backtest -> Canary -> Full` 순서와
전략 합격 관문을 우회하지 않는다. VII: 외부 API 접근 없음. VIII.A: 생산 배포와
무관하다. IX: 커널·주문 제한 변경 없음. 실제 자본 0, 주문 0.

## Design and rollback

1. `contracts/preregistration.json`에 원본 지문, 개발 세션, 한 신호와 비용을 봉인한다.
2. 고정 감사 결과에서 적격 사건을 선별하고 진입 세션별 중복을 분리한다.
3. 가격 CSV를 지문 검사하며 순차 스캔한다. 미래 기간의 수익은 열지 않는다.
4. 누락·가격쌍·두 비용 결과를 결정적 JSON으로 출력하고 단위 반례와 실제 자료로 검사한다.
5. 새 연구 경로에서 오류가 있으면 사용을 중단하고 포인터를 201로 되돌린다.

과거 공시 공개·정확한 기업 계보·체결 가능성이 증명되지 않았으므로 공식 T013
승격 기능은 구현하지 않는다. 기존 기능은 그대로 남는다.
