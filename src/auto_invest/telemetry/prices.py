"""Anthropic model price-table loader (R-T3, FR-T08, FR-T10).

The price table is operator-editable TOML at `config/llm_prices.toml`.
Unknown model names produce `cost_usd = None` (NOT 0) so downstream
queries can distinguish "free" from "we don't know yet".

The loader records a `PRICE_TABLE_LOADED` audit event with the file's
SHA-256 — see `cli.run` for the wiring.
"""

from __future__ import annotations

import hashlib
import tomllib
from decimal import ROUND_HALF_EVEN, Decimal
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

_MILLION = Decimal("1000000")
_QUANT = Decimal("0.000001")


class PriceEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    usd_per_million_input_tokens: Decimal = Field(ge=Decimal("0"))
    usd_per_million_output_tokens: Decimal = Field(ge=Decimal("0"))
    usd_per_million_cache_read_tokens: Decimal = Field(ge=Decimal("0"))
    usd_per_million_cache_write_tokens: Decimal = Field(ge=Decimal("0"))


class PriceTable(BaseModel):
    """Maps model name -> per-million-token prices (USD)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    entries: dict[str, PriceEntry]
    sha256: str
    source_path: str

    def compute_cost(
        self,
        model: str,
        *,
        input_tokens: int,
        output_tokens: int,
        cache_read_tokens: int,
        cache_write_tokens: int,
    ) -> Decimal | None:
        """Return USD cost as a Decimal quantized to 6 dp, or None if unknown."""
        entry = self.entries.get(model)
        if entry is None:
            return None
        total = (
            Decimal(input_tokens) * entry.usd_per_million_input_tokens
            + Decimal(output_tokens) * entry.usd_per_million_output_tokens
            + Decimal(cache_read_tokens) * entry.usd_per_million_cache_read_tokens
            + Decimal(cache_write_tokens) * entry.usd_per_million_cache_write_tokens
        ) / _MILLION
        return total.quantize(_QUANT, rounding=ROUND_HALF_EVEN)


class PriceTableError(ValueError):
    """Raised on missing file or schema violation."""


def load_prices(path: Path) -> PriceTable:
    """Load and validate the TOML price table."""
    if not path.exists():
        raise PriceTableError(f"price table not found: {path}")
    raw_bytes = path.read_bytes()
    try:
        raw = tomllib.loads(raw_bytes.decode("utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise PriceTableError(f"price table {path} is not valid TOML: {exc}") from exc

    entries: dict[str, PriceEntry] = {}
    for model, block in raw.items():
        if not isinstance(block, dict):
            raise PriceTableError(
                f"price-table entry for {model!r} must be a TOML table"
            )
        try:
            entries[model] = PriceEntry(**block)
        except (ValueError, TypeError) as exc:
            raise PriceTableError(
                f"price-table entry for {model!r} failed validation: {exc}"
            ) from exc
    if not entries:
        raise PriceTableError(f"price table {path} is empty")

    sha = hashlib.sha256(raw_bytes).hexdigest()
    return PriceTable(entries=entries, sha256=sha, source_path=str(path))
