# Implementation Plan: 관측 시점이 보존되는 실적 사건 입력

**Branch**: `codex/195-earnings-event-inputs` | **Date**: 2026-09-21 | **Spec**: [spec.md](spec.md)

## Summary

오프라인 원문 스냅샷과 검토한 사건 주장을 결합한다. 로컬 확인 시각 이후만 조회하며
게시·접수 시각으로 소급하지 않는다. 실제 두 원문은 2014년 조회에 사용 불가여야 한다.

## Technical Context

Python >=3.11 표준 라이브러리, JSON/원문 파일, pytest, ruff. macOS/Linux 오프라인 CLI.
작은 공시 묶음 대상으로 파일당 10MiB 상한, 외부 네트워크·브로커·비밀값 의존 없음.
사건의 수치/의미는 자동 추론하지 않는다. 원문 인용과 수동 검토 출처를 보존한다.

## Constitution Check

설계 전후 I–X 확인: 포지션/허용 목록 변경 없음(I/II), LLM 호출 없음(III),
운영 감사·대사 무변경(IV), 공개 원문만 사용(V), 연구 입력은 단계 승격 불가(VI/IX/X),
새 외부 호출 없음(VII), 기존 장중 배포 제한 유지(VIII.A). 커널 터치 없음.
누락된 홀드아웃·전진 관찰·캐너리·계좌 증거를 대체하지 않는다. 실제 자본 0.

## Project Structure

- `src/auto_invest/analytics/earnings_event_inputs.py`: 엄격 입력, 원문 스냅샷, 사건 버전, 기준 시점 조회.
- `scripts/earnings_event_inputs.py`: import/query 명령, 새 출력만 허용.
- `tests/unit/test_earnings_event_inputs.py`: 시간·변조·버전·누락 반례.
- `tests/integration/test_earnings_event_inputs_cli.py`: 실제 명령 흐름과 출력 보존.
- `specs/195-earnings-event-inputs/`: 계약·연구 결정·실제 검증 결과.

## Execution and rollback

먼저 명세/계약과 반례를 고정하고 구현한다. import는 입력 전체 검증 후 새 디렉터리에
동일 바이트 원문과 manifest를 저장한다. query는 원본 지문을 재검사한 뒤 같은 사건의
관측된 최신 버전만 반환한다. 출력에 live_eligible=false, strategy_admitted=false를 고정한다.
기존 기능 제거 없음. 되돌림은 새 CLI 미사용 및 명세 포인터 복원이며 원본/감사는 보존한다.
전체 회귀·린트·하네스·인계 검사 뒤 PR을 완료한다. 후속 역사 자료 확보와 전략 검증은 별도다.
