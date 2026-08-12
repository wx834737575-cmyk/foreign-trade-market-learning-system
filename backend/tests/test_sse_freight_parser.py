from datetime import date
from decimal import Decimal

import pytest

from app.parsers.sse_freight import parse_freight_index


def _html(code: str, row: str) -> str:
    return f"""
    <html><head><title>{code} - 上海航运交易所</title></head><body>
      <div>页面日期 2026-07-20</div>
      <table><tr><td>上期 2026-07-10</td><td>本期 2026-07-17</td></tr><tr>{row}</tr></table>
    </body></html>
    """


def test_parse_scfi_latest_composite() -> None:
    payload = _html(
        "SCFI",
        "<td>综合指数 Comprehensive Index</td><td></td><td></td><td>3184.83</td><td>3080.31</td><td>-104.52</td>",
    )
    result = parse_freight_index(payload, "SCFI")
    assert result.period == date(2026, 7, 17)
    assert result.previous_period == date(2026, 7, 10)
    assert result.value == Decimal("3080.31")


def test_parse_ccfi_latest_composite() -> None:
    payload = _html(
        "CCFI",
        "<td>中国出口集装箱运价综合指数</td><td>1873.15</td><td>1910.67</td><td>2.0</td>",
    )
    result = parse_freight_index(payload, "CCFI")
    assert result.value == Decimal("1910.67")
    assert result.change == Decimal("2.0")


def test_scfi_rejects_inconsistent_change() -> None:
    payload = _html(
        "SCFI",
        "<td>综合指数</td><td>3184.83</td><td>3080.31</td><td>-100.00</td>",
    )
    with pytest.raises(ValueError, match="涨跌额"):
        parse_freight_index(payload, "SCFI")
