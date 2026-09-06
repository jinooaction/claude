# 구현 계획: KIS 단타 실행

**Branch**: `codex/182-intraday-kis-execution` | **Date**: 2026-09-07
**Spec**: [spec.md](spec.md)

## Summary / Technical Context
Python, SQLite, httpx, pydantic, exchange_calendars, pytest를 재사용한다.
새 자료 계정과 패키지 의존성은 없다. 매분 관측과5분봉 판단,5종목, 한 고정 전략이다.
기존 OrderRouter/ExecutionAuthority/fill_sync를 공유하는 단타 coordinator를 만든다.
고유 claim과 이벤트는 추가전용 테이블이며 주문·체결은 기존 장부를 사용한다.
DB별 잠금 아래 재관측→대사→미체결 관리→매도→매수 순서를 지킨다.
실제 권한 제공자가 없으면 거절된다. CLI는 MockTransport를 직접 생성하는
오프라인 rehearsal만 제공한다. 외부 네트워크·기존 계좌DB·환경 비밀값은 사용하지 않는다.

## Constitution Check
I/II: 기존 router cap/whitelist + 단타20/20/80 상한, 현금·귀속수량 추가 확인.
III: 봉당LLM 없음. IV: 주문 전claim, 취소 전감사, broker 최종상태만 fills에 반영.
V/VII: 기존 인증·비밀값 정화·유한 읽기 재시도, 주문/취소 자동 재전송 금지.
VI/X: 자료/합격후보/60세션/실행동등성/강화캐너리/단타자본 승인이 아직 없으므로
생산 실주문 서비스와 권한을 추가하지 않는다. 기존 X.4 하루1회 경계 불변.
VIII/IX: 일반 PR/강화캐너리/장외배포, K4/K6 터치 감사. 헌법 변경 없음.
설계 전후 동일: 구현/격리시험 허용, 증거없는 생산 반복주문 차단.

## Project Structure
- `execution/intraday.py`: 계좌관측·고정목표·claim·실행상태와 귀속보유
- `execution/cancellation.py`: 단일취소 요청·불확정 유지, 기존 worker와 공유
- `broker/overseas.py`, `execution/authority.py`: 취소 필수인수/성공검사
- `persistence/audit.py`: 취소 요청/결과 감사형식
- `scripts/intraday_execution.py`: 격리 전체경로 검증명령
- `tests/unit/test_intraday_execution.py`, `tests/integration/test_intraday_execution_contract.py`

## 검증 순서 / Complexity Tracking
취소 계약·상태 시험→취소코드→단타 실행/복구 시험→coordinator→CLI→전체회귀.
취소 요청을 최종 취소로 취급하던 기능만 제거한다. 즉시 재호가는 없애고 실제 체결
동기화 뒤 다음 정상 판단이 새 목표를 계산한다. 원본 주문/부분체결/감사 보존.
독립 데이터 조사와 로컬 설계는 동시 진행했고 공유 파일 수정은 직렬이다.
자료 수집권한·756세션·합격전략·60세션·생산 활성화는 별도 외부관문이다.
