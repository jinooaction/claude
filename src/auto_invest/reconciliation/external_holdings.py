"""시스템 비관리 외부 보유 기준선 (external holdings baseline).

실계좌에는 시스템이 사고팔지 않는 운영자 소유 종목이 있을 수 있다 — 예:
시스템 가동 전부터 보유하던 주식(BHP·MRK·ORANY·RELX, 2026-05 이전 취득).
원장(fills → current_positions)은 시스템이 직접 체결한 것만 추적하므로 이
종목들은 영원히 "원장에 없는 보유"로 남고, 매 장 마감 정합성 검사가
MISMATCH → halt 를 무한 반복한다(2026-06-04·06-11 실측).

이 모듈은 그 보유를 **명시적 기준선** TOML 로 선언해 읽는다. 정합성 검사는
(원장 수량 + 기준선 수량) == 브로커 수량 을 대조하므로:

  * 기준선과 정확히 일치하면 OK — 깃발이 서지 않는다.
  * 수량이 1주라도 달라지면 여전히 MISMATCH → halt. 안전망 약화가 아니다 —
    시스템 모델 밖에서 무언가 움직였다는 신호이므로 멈추고 드러낸다(fail-safe).

가짜 체결(fills)을 끼워 넣어 원장에 흡수하지 않는 이유: fills 는 시스템
실행의 추가 전용 포렌식 진실(헌법 IV)이고, 합성 행은 감사 기록을 오염시키며
룰 워커가 자기 보유로 오인해 매도할 수 있다. "모르는 보유를 자동 입양"하지
않는 이유: 예기치 않은 계좌 활동을 조용히 흡수하면 안전망이 사라진다 —
기준선은 버전 관리되는 파일이라 변경 자체가 git 이력에 남는다.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from auto_invest.config.loader import ConfigError


class ExternalHoldingsError(ConfigError):
    """외부 보유 기준선 TOML 이 잘못된 경우 — 워커 시작을 막는다(fail-fast)."""


def load_external_holdings(path: Path) -> dict[str, int]:
    """기준선 TOML 을 symbol → qty 매핑으로 읽는다.

    파일이 없으면 빈 매핑 — "기준선 없음"은 정상 상태다(외부 보유가 없는
    계좌). 파일이 있는데 형식이 잘못됐으면 ExternalHoldingsError 로 시작을
    막는다 — 잘못 선언된 안전 기준선이 조용히 {} 가 되면 허위 halt 또는
    (더 나쁘게) 잘못된 통과가 나오기 때문.
    """
    if not path.exists():
        return {}

    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise ExternalHoldingsError(f"외부 보유 기준선 TOML 파싱 실패 ({path}): {exc}") from exc

    entries = raw.get("holdings", [])
    if not isinstance(entries, list):
        raise ExternalHoldingsError(f"{path}: 'holdings' 는 [[holdings]] 테이블 배열이어야 합니다.")

    holdings: dict[str, int] = {}
    for i, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ExternalHoldingsError(f"{path}: holdings[{i}] 가 테이블이 아닙니다.")
        symbol = entry.get("symbol")
        qty = entry.get("qty")
        if not isinstance(symbol, str) or not symbol.strip():
            raise ExternalHoldingsError(
                f"{path}: holdings[{i}].symbol 은 비어 있지 않은 문자열이어야 합니다."
            )
        symbol = symbol.strip().upper()
        # bool 은 int 의 하위 타입이므로 명시적으로 거른다(true/false 오타 방어).
        if isinstance(qty, bool) or not isinstance(qty, int) or qty <= 0:
            raise ExternalHoldingsError(
                f"{path}: holdings[{i}].qty 는 양의 정수여야 합니다 "
                f"(symbol={symbol!r}, qty={qty!r})."
            )
        if symbol in holdings:
            raise ExternalHoldingsError(
                f"{path}: 중복 symbol {symbol!r} — 항목당 한 번만 선언하세요."
            )
        holdings[symbol] = qty

    return holdings
