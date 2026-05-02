"""Whitelist — operator's deny-by-default allowlist (constitution II).

Symbols, accounts, order types, and sessions are all opt-in. Anything
not declared here is rejected by the risk gates before reaching the
broker.

Per `contracts/rules-config.md`, symbols are restricted to uppercase
A-Z and 0-9 only; the loader rejects any symbol that does not match.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from pydantic import BaseModel, ConfigDict, Field, field_validator

from auto_invest.config.enums import OrderType, Session

SYMBOL_PATTERN = re.compile(r"^[A-Z][A-Z0-9]{0,9}$")


class Whitelist(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    symbols: frozenset[str] = Field(default_factory=frozenset)
    accounts: frozenset[str] = Field(default_factory=frozenset)
    order_types: frozenset[OrderType] = Field(
        default_factory=lambda: frozenset({OrderType.LIMIT})
    )
    sessions: frozenset[Session] = Field(
        default_factory=lambda: frozenset({Session.REGULAR})
    )

    @field_validator("symbols", mode="before")
    @classmethod
    def _normalize_symbols(cls, value: Iterable[str] | None) -> frozenset[str]:
        if value is None:
            return frozenset()
        normalized: list[str] = []
        for s in value:
            if not isinstance(s, str):
                raise ValueError(
                    f"symbol must be a string, got {type(s).__name__}: {s!r}"
                )
            up = s.upper()
            if not SYMBOL_PATTERN.match(up):
                raise ValueError(
                    f"symbol {s!r} contains illegal characters; "
                    "allowed: A-Z and 0-9, must start with A-Z, max 10 chars"
                )
            normalized.append(up)
        if len(set(normalized)) != len(normalized):
            seen: set[str] = set()
            duplicates: list[str] = []
            for s in normalized:
                if s in seen:
                    duplicates.append(s)
                seen.add(s)
            raise ValueError(
                f"duplicate symbols in whitelist (after uppercasing): {sorted(set(duplicates))}"
            )
        return frozenset(normalized)
