from decimal import Decimal

import pytest

from app.metrics import percentage_change, scissors_gap


def test_percentage_change() -> None:
    assert percentage_change(Decimal("110"), Decimal("100")) == Decimal("10.00")
    assert percentage_change(Decimal("90"), Decimal("100")) == Decimal("-10.00")


def test_percentage_change_rejects_zero_base() -> None:
    with pytest.raises(ValueError):
        percentage_change(Decimal("1"), Decimal("0"))


def test_scissors_gap_is_percentage_points() -> None:
    assert scissors_gap(Decimal("4.0"), Decimal("8.0")) == Decimal("-4.00")

