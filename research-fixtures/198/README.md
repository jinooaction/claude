# 고정 개발 입력 — HF Data Library

데이터: Ahmed Elkassabgi, HF Data Library (2026),
[원본 데이터와 DOI](https://doi.org/10.5281/zenodo.19501605).
제공자가 명시한 [CC BY 4.0 이용 조건](https://hfdatalibrary.com/pages/license)과
[출처 표시 지침](https://hfdatalibrary.com/pages/cite)을 따른다.
원저자: Ahmed Elkassabgi. 데이터 원본과 편집본에 대한 보증이나 저자의 승인을 뜻하지 않는다.

2026-09-28 UTC에 확인한 공급자 조건은 편집·배포를 허용하며 2022년 이전 자료를
명시적으로 포함한다. 이 묶음은 PiTrading 기반 SPY·QQQ·IWM·TLT·GLD의
2013-08-23~2020-03-06 정규장 개발 구간만 포함한다. IEX 이후 자료는 없다.

원본 1분 OHLCV의 변경 사항: source=pitrading 선택, 위 날짜 및 XNYS 정규장 선택,
5분봉으로 시가 첫 값·고가 최댓값·저가 최솟값·종가 마지막 값·거래량 합계 집계,
현지 시각을 UTC로 변환. 빈 구간을 채우거나 조정 가격을 역산하지 않았다.
이는 이미 기존 연구에서 고정한 CSV 바이트의 gzip 포장본이며 새 자료 선택이 아니다.

`manifest.json`은 기존 원본 바이트와 동일하다. 압축을 해제한 다섯 CSV의 지문은
그 manifest와 일치해야 한다. `source_audit`는 최초 수집 환경의 감사 기록을 가리키는
보존된 메타데이터이며 이 묶음에 해당 외부 파일은 포함하지 않는다.
이 묶음의 무결성 확인은 manifest·CSV 지문과 별도 계약의 자료 지문으로 수행한다.

계좌·사용자 로그인·실제 주문 정보는 없다. 최종 확인용 495거래일도 없다.
조정 가격, 고정된 ETF 표본, 실제 체결 동등성 미확인 한계는 그대로다.
원격 연구 재현을 위한 입력이며 투자 추천이나 실거래 승인 자료가 아니다.

```sh
uv run python scripts/unpack_late_session_input.py --output-dir /tmp/late-session-input
uv run python scripts/late_session_probe.py develop --bars-dir /tmp/late-session-input --manifest /tmp/late-session-input/manifest.json --output-dir /tmp/late-session-result
uv run python scripts/late_session_probe.py verify --bars-dir /tmp/late-session-input --manifest /tmp/late-session-input/manifest.json --evidence /tmp/late-session-result
```
