"""Canonical hashing for backtest reproducibility (FR-B-001 / SC-002).

Two TOML files that differ only in whitespace, key order, or decimal
formatting MUST produce the same `config_hash`. The same is true of
rule snapshots; this is what lets a re-run of the same backtest hit
the idempotent path.

The canonicalisation is deliberately simple:

  1. Parse the TOML.
  2. Walk the tree, sort dict keys lexicographically.
  3. Normalise decimal *string* values (strip trailing zeros after
     the decimal point; never use scientific notation).
  4. Re-emit as a stable, line-oriented text form.
  5. SHA-256 of the canonical bytes.

We do not depend on a third-party canonical-TOML emitter. The
re-emit format here is *not* round-trip TOML — it is a canonical
text form just for hashing.
"""

from __future__ import annotations

import hashlib
import io
import tomllib
from decimal import Decimal, InvalidOperation
from typing import Any

_DECIMAL_RE_HINT = ("0123456789-.")


def _looks_like_decimal_string(s: str) -> bool:
    if not s:
        return False
    body = s.lstrip("-")
    if not body:
        return False
    if not all(c in _DECIMAL_RE_HINT or c.isdigit() for c in s):
        return False
    if "." not in s and not (s.lstrip("-").isdigit()):
        return False
    try:
        Decimal(s)
        return True
    except InvalidOperation:
        return False


def _normalise_decimal_string(s: str) -> str:
    d = Decimal(s)
    # Strip trailing zeros after the decimal point but keep one digit
    # before/after so "1.0" stays "1.0" (or "1" for integers).
    if d == d.to_integral_value():
        return str(d.quantize(Decimal(1)))
    text = format(d.normalize(), "f")
    # `format(..., "f")` keeps the original precision; trim trailing zeros.
    if "." in text:
        text = text.rstrip("0").rstrip(".") if text.endswith("0") else text
    return text


def _normalise(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _normalise(v) for k, v in sorted(value.items())}
    if isinstance(value, list):
        return [_normalise(v) for v in value]
    if isinstance(value, str) and _looks_like_decimal_string(value):
        return _normalise_decimal_string(value)
    return value


def _emit(value: Any, out: io.StringIO, indent: int = 0) -> None:
    pad = "  " * indent
    if isinstance(value, dict):
        for k in sorted(value.keys()):
            v = value[k]
            if isinstance(v, dict):
                out.write(f"{pad}{k}:\n")
                _emit(v, out, indent + 1)
            elif isinstance(v, list):
                out.write(f"{pad}{k}:\n")
                for item in v:
                    if isinstance(item, dict):
                        out.write(f"{pad}  -\n")
                        _emit(item, out, indent + 2)
                    else:
                        out.write(f"{pad}  - {_format_scalar(item)}\n")
            else:
                out.write(f"{pad}{k}: {_format_scalar(v)}\n")
    else:
        out.write(f"{pad}{_format_scalar(value)}\n")


def _format_scalar(v: Any) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if v is None:
        return "null"
    return str(v)


def canonicalise(text: str) -> str:
    """Parse `text` as TOML, return a deterministic textual canonical form."""
    raw = tomllib.loads(text)
    norm = _normalise(raw)
    out = io.StringIO()
    _emit(norm, out)
    return out.getvalue()


def config_hash(text: str) -> str:
    """SHA-256 of the canonicalised TOML, prefixed `sha256:`."""
    canon = canonicalise(text).encode("utf-8")
    return "sha256:" + hashlib.sha256(canon).hexdigest()


def rule_snapshot_hash(text: str) -> str:
    """Same canonical hash applied to a rule TOML."""
    return config_hash(text)


def run_id(*, rule_hash: str, config_hash_: str, data_pin_hash: str) -> str:
    """Compose the 12-char run_id from the three input hashes."""
    h = hashlib.sha256()
    h.update(rule_hash.encode("utf-8"))
    h.update(config_hash_.encode("utf-8"))
    h.update(data_pin_hash.encode("utf-8"))
    return h.hexdigest()[:12]


def data_pin_hash(pins: list[dict[str, Any]]) -> str:
    """Hash a list of `(asset_class, venue, symbol, vendor, as_of_ts_pin_utc)` pin dicts."""
    h = hashlib.sha256()
    for pin in sorted(pins, key=lambda p: (p["asset_class"], p["venue"], p["symbol"])):
        for k in sorted(pin.keys()):
            h.update(f"{k}={pin[k]};".encode("utf-8"))
        h.update(b"|")
    return "sha256:" + h.hexdigest()
