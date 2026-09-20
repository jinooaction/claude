# Implementation Plan: 급락 후 회복 확인 단타 연구

**Branch**: `codex/191-shock-recovery-research` | **Date**: 2026-09-21 | **Spec**: [spec.md](spec.md)

## Summary

기존177 체결 엔진에 새 연구 family만 추가하고191 전용 계약·개발 실행·원본 재계산
명령을 만든다. 기존177/190 레지스트리·비용·판정은 그대로 유지한다.
새 확인495일을 읽는 명령은 제공하지 않는다. 개발 선정은 확인검증 대기일 뿐이다.

## Technical Context

Python3.12, 기존numpy/거래일 달력/pytest/ruff. 새 의존성 없음.
입력은 지문 고정1645일 CSV/manifest, 출력은 새 디렉터리 JSON/JSONL이다.
4후보×2비용. 실제 개발 재생과 동일 모형 재계산을 별도로 수행한다.
기존 체결 모형의 전체 봉 거래량 사용·조정가격 한계는 신호 인과성과 구별한다.

## Constitution Check

설계 전/후 통과. I/II: 기존 종목·한도와 실제 주문 제한 불변.
III: 봉별 LLM 없음. IV/V: 감사 기록 불변, 비밀값 접근 없음.
VI: 자본0; 확인·60일 전진관찰·hardened canary·실행 동등성 대체 불가.
VII: 새 외부 API 없음. VIII.A: 장중 배포 제한 불변. IX: Kernel 무변경.
X: 측정된 실패도 보존한다. 위험 등급2: 연구 코드는 등급1이나 명세/AGENTS 포인터 갱신 포함.
제거 기능 없음. 실패하면191 사용 중단 및 변경 커밋 되돌림, 기존 증거는 보존한다.

## Project Structure

- `src/auto_invest/analytics/intraday_paper_challenger.py`: 새 순수 신호와 하루1시도.
- `src/auto_invest/analytics/shock_recovery_intraday.py`: 계약/후보/개발/재계산.
- `scripts/shock_recovery_probe.py`: `develop|verify`, 깨끗한 코드·지문·새 출력 검증.
- `tests/unit/test_shock_recovery_intraday.py`, `tests/integration/test_shock_recovery_cli.py`.
- 본 디렉터리의 계약·연구·자료 모델·작업표·실제 결과 기록.

## Verification

신호/엔진 반례와177/190 회귀를 우선 실행한다. 사전등록 커밋 이후에만191 성과를 연다.
원본 재계산 일치, 변조·덮어쓰기 거부, 갭/미체결/부분체결/당일 청산 실패를 검사한다.
전체 pytest/ruff 및 하네스/HANDOFF 검증 후 PR 마무리. 개발 재현은 최종 합격이 아니다.
