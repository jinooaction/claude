# Implementation Plan: 하락 개장 후 회복 검증

**Branch**: `codex/204-gap-reclaim-price` | **Date**: 2026-10-02 | **Spec**: [spec.md](spec.md)

## Summary

28개 고정 대형주의 하락 개장과 개장가 회복을 한 가설로 봉인한다. 194의30개
CSV를 전체 지문 검사하고 개발 구간의 고정 관측 시각만 압축해 전달한다.
가격쌍 진단·재계산·전체 회귀는 GitHub에서 수행한다. 양수 결과도 실제 전략 합격이 아니다.

## Technical Context

- Python3.11, 기존 exchange_calendars, Decimal, csv/gzip/hashlib. 새 의존성 없음.
- 원본: 저장소 밖 sparse-194-input-v1 약1GiB. 전달: research-fixtures/204의 고정시각 원문 행·원본 manifest·지문 잠금.
- 명령: scripts/gap_reclaim_price_diagnostic.py의 stage/score/verify.
- 시험: 작은 누락·시간·변조 반례와 정확한 PR 코드의 원격 전체 pytest/ruff.
- 성능: 한 파일씩 순차 준비, 1MiB마다 쉬는 구간과 nice19. 로컬 성과 계산/전체 검사 없음.
- 대상: 오프라인 연구와 읽기 전용 GitHub 실행. 계좌·외부 요청·주문 없음.

## Constitution Check

I/II: 연구 집단은 거래 허용 목록이 아니며 주문·자본·한도 변경 없음.
III: 실행 중 LLM 없음. IV/V: 거래 감사·비밀값 접근 없음, 공개 가격만 전달.
VI: 연구 진단은 Backtest/Canary/Full 자격을 대체하지 않음.
VII: 새 외부 호출 없음. VIII.A: 일반 배포 관문 유지.
IX: kernel/헌법 무변경. X: 기존 탈락 결과와 시행 수를 보존하며 새 가설은 성과 전 봉인.
177 합격 통계·실체결·60세션·live 지문·NAV가 없으면 자본0을 유지한다.
설계 후에도 같은 경계를 재검토했다. 위반·추가 안전 예외 없음.

## Project Structure

- specs/204-gap-reclaim-price: 명세·계획·연구·자료모델·명령·계약·작업·결과.
- scripts/gap_reclaim_price_diagnostic.py: 지문 확인/시각 축소, 계약/잠금 검증, 비용 진단·재계산.
- tests/unit/test_gap_reclaim_price_diagnostic.py: 시각·누락·변조·산술 반례.
- research-fixtures/204: CC BY4.0 출처와 개발 구간만의 원문 행 압축·잠금.
- .github/workflows/gap-reclaim-checks.yml: 정확한 커밋의 전체 회귀·실제 진단·증거 보존.

## Design and Verification

사전등록 커밋→작은 반례 구현→전체 원본 지문을 확인한 시각 축소→축소본 잠금
커밋→원격 개발/재계산·전체 검사→검토·병합·배포 감사→인계.
종목·거래일은 달력 전체로 고정한다. 전일 마감은 실제 종료−1분과 정확히
일치해야 한다. 신호 부재와 미래 참조 누락을 구분하며 반일장 청산 누락도 보존한다.
입력 압축은 크기 제한·고정 지문으로 검사한다.

## Delivery and rollback

기존 후보·수집 사슬·거래 경로를 제거하지 않는다. 신규 명령은 후속 PR로
수정/되돌리고 기존 원본·성과는 보존한다. 새 명령을 실행하지 않으면 기존 운용에
영향이 없다. 배포 실패는 기존 롤백 절차를 따른다.

## Complexity Tracking

30개 전체 CSV를 원격 저장소에 추가하지 않기 위해 고정시각 축소를 둔다.
자료 전달 단계이며 관측을 채우거나 유리한 가격을 선택하는 단계가 아니다.
