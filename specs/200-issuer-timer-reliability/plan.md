# Implementation Plan: 발행사 관측의 서버 정기 실행

**Branch**: `codex/200-issuer-timer-reliability` | **Date**: 2026-10-02 | **Spec**: [spec.md](spec.md)

## Summary

기존 GitHub 정기 실행은 13회 성공했지만 실제 간격이 174~438분이었다. 기존 서버에서
15분마다 Microsoft의 고정 RSS 목록을 관측한다. 같은 목록의 본문은 마지막 완전 검증 후
24시간 이내에만 재요청을 생략한다. 서버에는 별도 추가 전용 기록을 만들고 기존 GitHub
기록을 유지한다. 기존 제한 수집기와 발행 도구를 재사용하며 읽기 전용 상태와 원격
복구 사본을 검증한다.

## Technical Context

**Language/Version**: Python 3.11, Bash/systemd, GitHub Actions YAML
**Primary Dependencies**: 기존 httpx·표준 라이브러리·systemd, 새 실행 패키지 없음
**Storage**: `/var/lib/auto-invest-issuer-observations/store`의 불변 원본·관측·완료 기록;
별도 `automation/server-issuer-observations` 원격 브랜치
**Testing**: 모의 HTTP·시계·재시작·변조 시험, Linux 유닛 분석, 정확한 커밋의 원격 전체 pytest/ruff
**Target Platform**: 기존 Linux 서버, 원격 GitHub 검사; Mac 화면 조작·무거운 검사 금지
**Project Type**: 연구용 자동 수집과 읽기 전용 증거
**Performance Goals**: 정상 서버 24시간의 96회 중 92회 이상 20분 이내 시도 종료;
같은 목록의 본문은 24시간마다 최대 3개 재검증
**Constraints**: 외부 요청 간격 ≥1초·20초/요청·180초/실행·8MiB/응답·512MiB 전체·64MiB 예약;
KIS/계좌 환경 파일 미주입; 원격 보존 성공 전에는 복구 완료로 보고하지 않음
**Scale/Scope**: Microsoft 한 회사·RSS 1개·실행당 본문 최대 3개, 단일 서버 작성자

## Constitution Check

- I/II/VI/X: 거래허용종목·전략·자본·승격무접촉. 원본회사선택은매매허용목록이아니다.
- III: 실행중LLM호출없음.
- IV/V: 거래감사/비밀값무접촉. 수집서비스에기존계좌환경파일을주입하지않고
  원격사본은공개발행사원본·관측만담는다.
- VII: 기존유한재시도·403즉시중단·15분냉각·출처/속도/용량한도를완화하지않는다.
- VIII.A: 일반배포의장중금지유지. 타이머설치와코드배포의순서를구분한다.
- IX: 커널목록무변경. 고정SSH읽기명령·유닛동기화는운영/외부경계변경으로
  위험등급3을적용한다. 권한입력·고정경로·출력·롤백을검증한다.
- 원본성: 서버사슬은GitHub사슬과다른출처다. 달력누락을과거관측으로채우지않는다.
  잔존원본은실패시보존하고타이머만중단할수있다.

## Project Structure

- `src/auto_invest/market_data/issuer_filings.py`: 기존수집기의선택적동일목록생략.
- `src/auto_invest/analytics/filing_observations.py`: 옛두필드/새세필드선택계약동시검증.
- `scripts/filing_observations.py`: 서버전용고정명령·읽기전용상태. 기존GitHub명령은유지.
- `deploy/auto-invest-issuer-observations.service`, `.timer`: 계좌환경없는제한서비스와15분달력.
- `deploy/issuer-observations-on-instance.sh`: 고정run ID,요청전용량·버전검사,서비스호출.
- `deploy/sync-units.sh`: 새두유닛만동기화·활성,기존거래서비스무재시작.
- `deploy/observe-on-instance.sh`: 고정읽기전용상태/내보내기,임의경로·명령금지.
- `.github/workflows/server-issuer-observations-backup.yml`: 기존제한SSH로서버사본을
  읽어검증하고별도브랜치에증분추가·90일복구산출물보존. GitHub지연은서버관측을막지않음.
- `tests/unit/`, `tests/integration/`: 원본불변·시계·중복·본문생략/재검증·권한·서비스시험.
- `specs/200-issuer-timer-reliability/`: 명세·계획·모델·계약·작업·결과.

## Design and Verification

1. 원격13회실행의간격과파일성장을기준으로고정한다. 같은RSS는동일blob1개였고
   54본문관측이54blob을만들었다. 현재512MiB/64MiB예약을그대로쓴다.
2. 서버전용수집은RSS원문을매번받아영수증을남긴다. 검증된목록바이트가동일하고
   이전완전본문검증이24시간안에있고직전실패가없을때만본문3개를생략한다.
   `selection.unchanged`는`unselected`·`limit_skipped`와분리하고과거2필드사슬도검증한다.
   이전원본을다시사용해새본문을본것처럼기록하지않는다.
3. 예정시각자체는관측시각이아니다. systemd달력15분,동시실행1개,실행180초미만,
   정확한시계상태를확인한다. 누락·서비스실패는읽기전용상태에서감지한다.
   공시공개초나정확한즉시성은추정하지않는다.
4. 서버서비스는`auto-invest`계정이지만계좌`.env`를읽지않는다.고정출처·고정설정·
   고정StateDirectory만읽고쓴다. 서비스비활성/코드롤백으로실행을중단하며
   기존사슬은삭제하지않는다. 배포가장중연기되면새코드설치전서비스가동을거부한다.
5. 서버원본을읽는SSH명령은고정`status`와고정디렉터리의검증된내보내기만허용한다.
   원격백업은기존GitHubSSH비밀값을재사용하지만서버에는GitHub쓰기토큰을추가하지않는다.
   GitHub작업은전체원본검증→기존별도브랜치와대조→증분artifact→추가전용게시순서다.
   실패/변조/기준불일치는원본·원격사본을바꾸지않고실패로기록한다.
6. 관련모의검사/리눅스systemd분석→원격전체pytest/ruff/하네스/인계→PR품질관문→
   병합·배포감사→첫실제수집두회·원격복구지문대조→24시간일정관찰순으로출시한다.
   서버가동증거가없으면명세완료로표시하지않는다.

## Delivery and rollback

기존GitHub `automation/issuer-observations`는유지한다. 새서버원본은독립자료이며
GitHub사본도별도브랜치다. 배포전에는모의시험과정확한커밋검사를끝낸다.
수집기는읽기전용HTTP이고서비스에KIS비밀값이나주문명령이없다. 중지시에는새타이머를
비활성화하고기존추가전용원본/원격사본을보존한다.잘못된코드는일반배포상태기계가
기존배포커밋으로되돌리며장중긴급경로는사용하지않는다. 원격백업일정이늦으면
서버관측은계속되고백업신선도경고가드러난다.복구로과거가용시각을만들지않는다.

## Complexity Tracking

추가서버사슬은GitHub `schedule`이실측174~438분간격이어서15분관측을제공하지
못하기때문에필요하다. 기존GitHub수집은별도대조/백업계열로남긴다.
원격백업은서버단독고장시관측증거가사라지는문제를막기위한추가경로다.
