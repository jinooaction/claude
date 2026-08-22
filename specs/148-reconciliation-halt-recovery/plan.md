# Implementation Plan: 정합성 중지의 조건부 자동 복구

**Branch**: `Codex/148-reconciliation-halt-recovery` | **Date**: 2026-08-22 | **Spec**: [spec.md](spec.md)

## Summary

기존 정합성 검사와 읽기 전용 복구 준비도 판정을 결합한 원자적 복구 서비스를 추가한다. production은 root 소유 고정 helper를 통해 이를 실행하고 sidecar를 남긴다. money-path는 그 sidecar를 최우선 안전 증거로 소비하여 halt가 있거나 증거가 낡으면 주문 가능 상태를 절대 보고하지 않는다.

## Technical Context

**Language/Version**: Python 3.11, Bash, GitHub Actions YAML
**Primary Dependencies**: Typer, Pydantic, SQLite, KIS broker adapter
**Testing**: pytest, ruff, bash syntax, workflow parser/static assertions
**Target Platform**: GitHub Actions와 Linux production worker
**Constraints**: 복구 실행 주문 0건, 정합성 halt만 조건부 해제, 감사 로그 추가 전용, fixed-command SSH

## Constitution Check

- I/II/III: whitelist, 포지션 한도, 주문 제한을 변경하지 않는다.
- IV: halt 해제 이유와 정합성 증거를 추가 전용 감사 로그에 남긴다.
- V: 새 비밀값을 만들거나 출력하지 않는다.
- VI/VIII.A: 정합성 오류 외 halt와 단계적 실거래 전환을 우회하지 않는다.
- IX/X: 기존 운영자 위임 안에서 절차를 자동화하되, 최신 증거가 없으면 차단한다.
- 위험 등급 4: live 주문 가능 판정과 halt 해제 경로를 변경한다.
- 되돌림: 자동 워크플로와 gateway 명령, money-path 복구 입력을 되돌리고 서버의 직접
  `resume --confirm` 비상 경로를 유지한다. 이미 추가된 감사 행은 보존한다.

## Design Decisions

1. 기존 `resume --confirm`은 비상 수동 도구로 남기고 자동화에서는 호출하지 않는다.
2. 복구기는 시작 때 읽은 halt와 해제 직전 halt가 정확히 같아야 한다.
3. 감사 기록 실패 시 원래 halt를 복원한다.
4. 복구 sidecar는 실제 전역 halt의 권위 있는 운영 증거이며, 누락도 차단으로 취급한다.
5. production SSH는 인자 없는 고정 명령만 허용한다.
