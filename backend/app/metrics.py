from decimal import Decimal, ROUND_HALF_UP


def percentage_change(current: Decimal, previous: Decimal) -> Decimal:
    if previous == 0:
        raise ValueError("比较期数值不能为零")
    return ((current - previous) / previous * Decimal("100")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )


def scissors_gap(m1_yoy: Decimal, m2_yoy: Decimal) -> Decimal:
    """M1-M2 剪刀差，单位为百分点。"""
    return (m1_yoy - m2_yoy).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def direction(current: Decimal, previous: Decimal) -> str:
    if current > previous:
        return "up"
    if current < previous:
        return "down"
    return "flat"

