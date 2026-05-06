"""T015 — shared conformance scaffold for every IngestionAdapter.

Adapters register themselves in `ADAPTERS` by decorating their class
with `@register_adapter`. This module parametrises a small set of
behavioural tests over the registry. Each adapter's PR adds its own
recorded fixtures and registers itself; the test then activates for
that adapter automatically.

When the registry is empty (early in spec 002 implementation), the
scaffold is a no-op — no failures, no spurious passes.
"""

from __future__ import annotations

import pytest

from auto_invest.market_data.adapters import ADAPTERS


def _adapter_ids() -> list[str]:
    return sorted(ADAPTERS.keys())


def _adapter_classes():
    return [ADAPTERS[name] for name in _adapter_ids()]


@pytest.mark.parametrize("adapter_cls", _adapter_classes(), ids=_adapter_ids() or ["<no-adapters-registered>"])
def test_adapter_declares_required_class_attributes(adapter_cls) -> None:
    if not _adapter_classes():
        pytest.skip("no adapters registered yet")
    assert isinstance(adapter_cls.name, str) and adapter_cls.name
    assert isinstance(adapter_cls.vendor, str) and adapter_cls.vendor
    assert isinstance(adapter_cls.supported_asset_classes, tuple)
    assert all(isinstance(x, str) for x in adapter_cls.supported_asset_classes)
    assert isinstance(adapter_cls.supported_kinds, tuple)
    assert all(isinstance(x, str) for x in adapter_cls.supported_kinds)
    assert isinstance(adapter_cls.needs_auth, bool)
