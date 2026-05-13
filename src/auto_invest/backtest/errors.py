"""Backtest engine exception hierarchy.

Each subclass maps to a documented CLI exit code per
contracts/cli.md. The engine's try/except wrapper uses the type
to choose the BACKTEST_FAILED `phase` label per FR-B16.
"""

from __future__ import annotations


class BacktestError(Exception):
    """Base for every spec-008 engine error."""


class OhlcvDataQualityError(BacktestError):
    """A required bar is NaN, has zero volume on a non-holiday, or unadjusted."""


class OhlcvVendorError(BacktestError):
    """Vendor transport / auth / rate-limit failure that survived retry."""


class OhlcvWindowError(BacktestError):
    """Vendor returned no bars for a window that should not be empty."""


class BacktestKernelTouchError(BacktestError):
    """The change-set diff intersects `.specify/memory/kernel.toml` paths.

    Defense-in-depth check; mirrors spec 007 FR-C08. Maps to CLI exit 7.
    """


class BacktestDirtyTreeError(BacktestError):
    """Working tree is dirty and `--allow-dirty` was not set. CLI exit 6."""


class BacktestReproducibilityError(BacktestError):
    """A deterministic post-condition failed (FR-B12)."""
