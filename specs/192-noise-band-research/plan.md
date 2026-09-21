# Implementation Plan: 과거 시각 변동 폭 단타 연구

**Branch**: `codex/192-noise-band-research` | **Date**: 2026-09-21 | **Spec**: [spec.md](spec.md)

## Summary
192 전용 신호·개발·재계산 명령을 만든다. 기존 체결 엔진은 noise_band에만
명시적 진입/청산 매핑을 받는다. 기존 family에 매핑을 전달하면 거부한다.
기존 신호/비용 산술은 유지한다. 495일 확인 명령은 없다.

## Technical Context
Python3.11/uv와 기존 exchange_calendars/numpy/pytest/ruff. 새 의존성 없음.
입력 고정1645일 CSV, 후보1×두비용, 새 JSON/JSONL 출력.
실제 직전 XNYS14세션의 동일 bar_index만 사용하며 세션/슬롯 누락은 무신호다.
입력1645일과 준비14일을 제외한 성과1631일을 구분한다.

## Constitution Check
설계 전후 통과. I/II: 종목/노출/주문 제한 보존. III: 봉별 LLM 없음.
IV/V: 감사/비밀값 무변경. VI: 자본0, 확인·전진·캐너리·실행 증거 대체 불가.
VII: 실행 중 외부 API 없음. VIII.A/B: 배포 경계 불변. IX: Kernel 무변경.
X: 사전등록/실패 보존. 등급2(연구1+AGENTS/명세포인터2). 제거 기능 없음.
문제 시192 사용 중단·커밋 되돌림, 기존 증거는 보존한다.

## Project Structure
- `src/auto_invest/analytics/noise_band_intraday.py`: 계약/인과적신호/개발/재계산.
- `src/auto_invest/analytics/intraday_paper_challenger.py`: noise_band 한정 매핑·매수시도·청산 지속.
- `scripts/noise_band_probe.py`: develop/verify, 깨끗한 코드와 새 출력만 허용.
- `tests/unit/test_noise_band_intraday.py`, `tests/integration/test_noise_band_cli.py`.

## Verification
평균/갭/동일가/미래불변/DST/반일장/누락/잘못된매핑/부분청산 반례와 기존 회귀.
계약 커밋 후 실제 개발/재계산, 전체 pytest/ruff, 하네스/HANDOFF/PR관문.
