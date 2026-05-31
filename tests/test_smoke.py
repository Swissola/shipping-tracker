"""Smoke tests for the shipping-tracker package.

Verifies importability, entry point behavior, and pluggable parser scaffold.
All test data is synthetic — no real tracking numbers or personal data.
"""

import subprocess

import pytest

from shipping_tracker.parsers.base import BaseParser, TrackingInfo


def test_package_importable() -> None:
    """The shipping_tracker package is importable without error."""
    import shipping_tracker

    assert hasattr(shipping_tracker, "__name__")


def test_parsers_subpackage_importable() -> None:
    """BaseParser and TrackingInfo are importable from the parsers sub-package."""
    assert BaseParser is not None
    assert TrackingInfo is not None


def test_base_parser_is_abstract() -> None:
    """BaseParser cannot be instantiated directly — it is abstract."""
    with pytest.raises(TypeError):
        BaseParser()  # type: ignore[abstract]


def test_tracking_info_dataclass() -> None:
    """TrackingInfo stores tracking_number and carrier as a dataclass."""
    ti = TrackingInfo(tracking_number="FAKE123", carrier="FAKECARRIER")
    assert ti.tracking_number == "FAKE123"
    assert ti.carrier == "FAKECARRIER"


def test_entry_point_exits_zero() -> None:
    """python -m shipping_tracker exits with return code 0."""
    result = subprocess.run(
        ["python", "-m", "shipping_tracker"],
        capture_output=True,
    )
    assert result.returncode == 0


def test_entry_point_no_stdout() -> None:
    """python -m shipping_tracker produces no stdout output (cron silence — D-07)."""
    result = subprocess.run(
        ["python", "-m", "shipping_tracker"],
        capture_output=True,
    )
    assert result.stdout == b""
