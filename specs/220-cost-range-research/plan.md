# Implementation Plan: 비용 범위 선별 단일 연구
**Branch**: codex/220-cost-range-research | **Date**: 2026-10-17 | **Spec**: [spec.md](spec.md)
## Summary
기존30분돌파에비용을덮는개장범위조건하나를추가한단일후보를사전등록하고원격에서만평가한다.
## Technical Context
Python3.11·기존paper/비용/metrics·pytest/ruff·exchange_calendars.새의존성없음.
기존research-fixtures/198(1645개발세션)·고정unpack경로.정확원격HEAD,읽기권한,비밀0.
## Constitution Check
설계전후 I~VII/VIII.A/IX/X 보존.등급3연구·풀SDD.생산커널/헌법/주문/자본/등록/허용목록변경0.
기존143달러예약복구승인은새단타활성화승인으로해석하지않는다.
기존실행registry와정확지문·60세션·90초·HMAC·EDGE_CONFIRMED·강화캐너리조건유지.
## Project Structure
src/auto_invest/analytics/cost_range_intraday.py: 봉인계약·후보·인과적신호·개발/검증.
src/auto_invest/analytics/intraday_paper_challenger.py: 새signal_plan family형식검사·1회시도목록만확장.
scripts/cost_range_probe.py: develop/verify,깨끗한정확코드·원본재생.
tests/unit/test_cost_range_intraday.py 및 tests/integration/test_cost_range_cli.py.
.github/workflows/cost-range-research.yml: 정확원격전체회귀·개발·독립검증/원본artifact.
## Phase 0 / 1
research.md·data-model.md·contracts/preregistration.json·quickstart.md가판단과입출력을정의한다.
원래198manifest를가격읽기전에확인한다.원래후보·연구결과를새후보로재표기하지않는다.
## Phase 2 / Test and release
사전등록커밋/푸시→합성인과성/실제CLI반례→원격전체검증/원본양비용재생→독립재계산→원래증거보존→merge/인계.
성과가음수이면계약을고쳐재탐색하지않는다.양성도후속확인필요이며프로그램전체완료가아니다.
## Rollback
새연구모듈/명령/워크플로/신호family추가만되돌린다.기존기능제거0.원본/계약/실패결과는감사근거로보존한다.
