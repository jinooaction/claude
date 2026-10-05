# Implementation Plan: 보관 분봉의 운영 관측 연결 검증

**Branch**: `codex/208-public-minute-bridge` | **Date**: 2026-10-06 | **Spec**: [spec.md](spec.md)

## Summary

207 보관6자산의 원격/전체 지문과 인증을 다시 확인하고 개발 두 월의 운영5ETF/5분 구간을 검사한다.
가격은 내부 집계/정규화에만 사용한다. 결과는 날짜·개수·누락·모형 시각이며 성과나 거래 자격이 아니다.

## Technical Context

Python3.11, 기존DuckDB/pandas/exchange_calendars/httpx 및 고정 연구 cryptography requirements.
저장소는 추가전용 safeJSON/기존207 암호문. pytest 합성/전체 XML, ruff, 하네스/인계/본문 관문.
Linux GitHub runner에서 전체514450366바이트를 재인증한다. Mac에서는 합성/작은파일만 처리한다.
두 월×21거래일×5종목, 메모리2GB DuckDB/2스레드, 실제 분석25분 제한/첫시도 하나.
새 의존성/생산 주문 호출부/헌법/커널 변경 없음.

## Constitution Check

구현 전 PASS: I한도/II허용종목/IV추가전용기록/V키격리/VI단계/VIII.A장중배포/IX자율/X측정 경계 보존.
현재5ETF를 새제공자 이름으로 승격하지 않는다. 최소36시도/31·40bp/200거래/현금·정산·부분체결/최종495세션 유지.
등급3: 키를 받은 복호화 경로와 첫시도 관문. 돈 경로 없음. this changes the safety perimeter를 커밋에 기록한다.
설계 후 PASS: 정확 검토SHA/owner·영구선점 전에는 키 접근 없음, 입력 6자산 고정, 원본/자산 덮어쓰기 없음.
실측되지 않은 공개 봉시각/게시지연/실행동등성/출처·라이선스는 false/미확인으로 유지한다.

## Project Structure

- `src/auto_invest/market_data/public_minute_bridge.py`: 순수분 집계/실제 달력/공통 날짜와가격 없는 진단.
- `scripts/public_minute_bridge.py`: 고정보관물/원격digest·207AEAD재사용·전체평문SHA·안전결과.
- `.github/workflows/public-minute-bridge.yml`: 전체회귀 후검토SHA/첫시도/보관물 분석·새 안전결과 보관.
- `tests/unit/test_public_minute_bridge.py`, `tests/integration/test_public_minute_bridge_cli.py`: 실패/인증/미래관측 반례.
- 이 폴더의 research/data-model/contracts/quickstart/tasks: 판단·검증·완료 기록.

## Failure / rollback / replacement

기존기능 제거 없음. 오류는 입력 인증과분석 상태를 분리한 영수증을 남기며 가격/비밀을 출력하지 않는다.
새 PUBLIC_MINUTE_BRIDGE_SHA 변수 제거로 실제 분석을 중지한다. 코드 되돌림은 정상 revert PR이며 기존 기록은 보존한다.
실행이 실패하면 같은SHA 자동재개하지 않는다. 종료/타임아웃/핸들실종은 실제 상태로 구분한다.

## Implementation / validation

반례 먼저 실패 확인→구현→짧은오프라인합성→린트/하네스/인계·본문→커밋/PR→원격전체XML→실제보관물분석.
원래207 분누락/일별실제교집합/모형 availability를 대조하고 결과원격SHA 확인한다.
완료 증거만 PR본문에 갱신해 문서 변경과 전체 검사의 반복을 만들지 않는다.

## Complexity Tracking

헌법 예외 없음. 모형 검증과 제공자/전략 자격을 분리하는 기존 방식을 그대로 따른다.
