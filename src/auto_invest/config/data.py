"""Spec 002 data-source configuration (FR-D-001, FR-D-003).

Loaded from `config/data.toml` via the same `tomllib` + Pydantic v2
plumbing as spec 001. Deny-by-default: an adapter not listed in
`enabled_adapters` cannot be invoked even if its module is importable.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Mapping

from pydantic import BaseModel, ConfigDict, Field, field_validator
import tomllib


class DataSourcesConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "002.1"
    enabled_adapters: tuple[str, ...] = Field(default_factory=tuple)
    default_vendor_per_kind: Mapping[str, str] = Field(default_factory=dict)
    vendor_disagreement_tolerance_bps: Decimal = Decimal("10")

    @field_validator("enabled_adapters", mode="before")
    @classmethod
    def _coerce_enabled(cls, value: object) -> tuple[str, ...]:
        if value is None:
            return ()
        if isinstance(value, (list, tuple)):
            return tuple(str(v) for v in value)
        raise TypeError("enabled_adapters must be a list of strings")

    @field_validator("default_vendor_per_kind", mode="before")
    @classmethod
    def _coerce_defaults(cls, value: object) -> Mapping[str, str]:
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise TypeError("default_vendor_per_kind must be a table")
        out: dict[str, str] = {}
        for key, val in value.items():
            if not isinstance(key, str) or ":" not in key:
                raise ValueError(
                    f"default_vendor_per_kind keys must be 'asset_class:kind' strings, got {key!r}"
                )
            out[key] = str(val)
        return out

    @field_validator("vendor_disagreement_tolerance_bps", mode="before")
    @classmethod
    def _coerce_tol(cls, value: object) -> Decimal:
        if isinstance(value, Decimal):
            return value
        if isinstance(value, (str, int)):
            return Decimal(str(value))
        if isinstance(value, float):
            raise TypeError(
                "vendor_disagreement_tolerance_bps must be a string-decimal, not a float literal"
            )
        raise TypeError(f"unsupported type for vendor_disagreement_tolerance_bps: {type(value)!r}")

    def vendor_for(self, asset_class: str, kind: str, *, override: str | None = None) -> str | None:
        """Resolve the vendor for `(asset_class, kind)`. Override wins."""
        if override is not None:
            return override
        return self.default_vendor_per_kind.get(f"{asset_class}:{kind}")


def load_data_sources(path: str | Path) -> DataSourcesConfig:
    """Load and validate `config/data.toml`. Caller chooses the path."""
    p = Path(path)
    raw = tomllib.loads(p.read_text(encoding="utf-8"))
    return DataSourcesConfig.model_validate(raw)
