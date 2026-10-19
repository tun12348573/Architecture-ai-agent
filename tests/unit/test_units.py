import pytest

from exterior_agent.domain.units import to_metres


def test_mm_to_metres():
    assert to_metres(4500, "mm") == pytest.approx(4.5)


def test_feet_to_metres():
    assert to_metres(1, "ft") == pytest.approx(0.3048)


def test_unknown_unit_raises():
    with pytest.raises(ValueError):
        to_metres(1, "yd")
