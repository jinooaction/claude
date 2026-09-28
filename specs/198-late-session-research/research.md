# 설계 판단

## 후보 선택

**Decision**: 기존 다섯 ETF에서 종료 30분 전 한 번 판단하는 매수 전용 후보.
**Rationale**: 공시 과거 관측 시각·DD/UTX 법인 연결이 필요 없어 다른 자료 경로를 연다.
**Alternatives considered**: 194 문제 종목 사후 삭제나 비용 인하는 실패한 가설을
살리는 선택이므로 제외한다. 기존 개장 돌파·회복·변동 폭과 진입 시점은 다르지만
넓게는 모멘텀 가설이며 독립된 발견이라고 과장하지 않는다.

설계 초안 `late-session-candidate-design-20260928.md`는 성과 조회 전에 작성했다.
이번 명세 작업에서는 가격 파일을 열지 않았다.

## 문헌 근거의 범위

- Gao·Han·Li·Zhou, [Market Intraday Momentum](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2440866):
  이전 조사에서 저자 초록을 확인했다. 첫 30분과 마지막 30분 관계가 동기다.
  해당 PDF 전체를 읽었다고 주장하지 않는다.
- Baltussen·Da·Lammers·Martens, [Hedging demand and market intraday momentum](https://academicweb.nd.edu/~zda/intramom.pdf):
  이전 조사에서 저자 공개 PDF 인쇄 377~379쪽을 확인했다. 마지막 구간 이전 움직임을
  이용하는 설계 동기다. 선물·양방향 연구이므로 ETF 매수 전용 후보의 재현이 아니다.

문헌 자료 기간 일부가 최종 확인 구간과 겹친다. 문헌이나 반복 조회한 개발 표본은
새 독립 검증 증거가 아니다. 기존 최소 31회 시도에 이번 한 회를 더한다.

## 시간과 체결

**Decision**: 신호 봉 완료와 다음 봉 시작이 같은 시각일 수 있음을 명시한다.
**Rationale**: `simulate_candidate`는 다음 봉 시작을 실행 가능 시점으로 기록하고
체결 봉 전체 거래량으로 부분 체결을 제한한다. 5분 추가 지연을 임의 변경하지 않는다.
**Alternatives considered**: 같은 봉 종가 체결·16:00 종가 경매는 제외한다.

고정 일별 배정은 실제 계좌 결제 장부와 동등하다는 증거가 아니다. 마이크로초 체결
시각도 관측 원본이 아니다. 최종 봉 부분 청산 잔여 수량은 실패로 남긴다.

## 재사용과 검증

**Decision**: 192 계약/재계산 구조와 190의 고정 개발 판정을 재사용한다.
**Rationale**: 비용 산술 복제 없이 기존 계열 회귀 시험으로 영향을 제한한다.
**Alternatives considered**: noise_band 이름으로 새 가설을 숨기지 않고 late_session을 추가한다.
새 의존성과 외부 API는 필요 없다. 무거운 전체 검증은 사용자 Mac 대신 원격 CI의
정확한 커밋 결과를 확인한다. 실제 재생도 자원을 분리한 실행 위치부터 확인한다.

## 원격 계산용 개발 자료 전달

**Decision**: 사전등록 개발 파일만 출처를 표시한 압축 검증 자료로 제공한다.
**Rationale**: 공급자 [license](https://hfdatalibrary.com/pages/license)는 CC BY 4.0의
범위에 2022년 이전 자료를 명시한다. [cite](https://hfdatalibrary.com/pages/cite)는
그 구간의 원천을 PiTrading으로 구분한다. 2026-09-28 UTC 본문을 확인했다.
**Alternatives considered**: 운영 서버의 제한 명령을 우회하지 않는다. 기존 SSH
원격 Mac은 접속 시도에서 시간 초과였다. 로그인 화면을 조작하거나 현재 Mac에서
대량 연구 계산을 실행하지 않고 기존 GitHub CI에서 처리한다.

입력 준비는 기존 5개 CSV의 지문·7개 필드·날짜 범위·행 수를 검사하고 압축 포장만
했다. 각 127,734행, 총 638,670행이며 전략 성과 계산은 수행하지 않았다.
후보 결과에 따라 구간이나 파일을 바꾸지 않도록 원본 manifest 바이트를 유지한다.
