"""외부 보유 기준선 로더 단위 테스트 (시스템 비관리 보유 — 정합성 허위 halt 종결).

기준선은 안전 장치의 입력이므로 로더는 엄격해야 한다: 파일 없음 = 정상(빈
기준선), 파일 있는데 형식 오류 = fail-fast (조용히 {} 가 되면 허위 halt 또는
잘못된 통과가 난다).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from auto_invest.config.loader import ConfigError
from auto_invest.reconciliation.external_holdings import (
    ExternalHoldingsError,
    load_external_holdings,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def _write(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "external-holdings.toml"
    p.write_text(body, encoding="utf-8")
    return p


def test_missing_file_means_empty_baseline(tmp_path: Path) -> None:
    assert load_external_holdings(tmp_path / "absent.toml") == {}


def test_valid_file_parses_to_mapping(tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        """
        [[holdings]]
        symbol = "BHP"
        qty = 1

        [[holdings]]
        symbol = "mrk"
        qty = 3
        """,
    )
    # symbol 은 대문자로 정규화된다(브로커 응답과 대조 가능해야 함).
    assert load_external_holdings(p) == {"BHP": 1, "MRK": 3}


def test_empty_holdings_list_is_empty_baseline(tmp_path: Path) -> None:
    assert load_external_holdings(_write(tmp_path, "holdings = []")) == {}


@pytest.mark.parametrize(
    "body",
    [
        'holdings = "not-a-list"',
        "[[holdings]]\nqty = 1",  # symbol 누락
        '[[holdings]]\nsymbol = ""\nqty = 1',  # 빈 symbol
        '[[holdings]]\nsymbol = "BHP"',  # qty 누락
        '[[holdings]]\nsymbol = "BHP"\nqty = 0',  # 0 수량
        '[[holdings]]\nsymbol = "BHP"\nqty = -1',  # 음수
        '[[holdings]]\nsymbol = "BHP"\nqty = 1.5',  # 정수 아님
        '[[holdings]]\nsymbol = "BHP"\nqty = true',  # bool 은 int 하위 타입 — 명시 거부
        '[[holdings]]\nsymbol = "BHP"\nqty = 1\n[[holdings]]\nsymbol = "BHP"\nqty = 2',  # 중복
        "holdings = [1, 2]",  # 항목이 테이블 아님
        "symbol = [broken",  # TOML 자체 오류
    ],
)
def test_malformed_baseline_fails_fast(tmp_path: Path, body: str) -> None:
    with pytest.raises(ExternalHoldingsError):
        load_external_holdings(_write(tmp_path, body))


def test_error_is_config_error_subclass() -> None:
    # CLI 의 기존 `except ConfigError` 분기가 그대로 잡도록 보장한다.
    assert issubclass(ExternalHoldingsError, ConfigError)


def test_deployed_baseline_file_is_valid() -> None:
    """운영 파일(deploy/external-holdings.toml)이 로더 검증을 통과하는지 CI 고정.

    수량까지 핀하지는 않는다 — 보유 변경 시 이 파일만 갱신하면 되도록.
    (수량 드리프트는 정합성 검사가 라이브에서 MISMATCH 로 잡는다.)
    """
    deployed = REPO_ROOT / "deploy" / "external-holdings.toml"
    holdings = load_external_holdings(deployed)
    assert holdings == {"ORANY": 28}
    assert all(qty > 0 for qty in holdings.values())
