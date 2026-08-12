from datetime import date, datetime
from decimal import Decimal

import pytest

from app.parsers.nbs_pmi import parse_nbs_pmi


def _fixture_html(title: str = "2026年6月中国采购经理指数运行情况 - 国家统计局") -> str:
    rows = "".join(
        f"<tr><td>2026年{month}月</td><td>{value}</td><td>51.0</td><td>50.0</td></tr>"
        for month, value in [(1, "49.3"), (2, "49.0"), (3, "50.4"), (4, "50.3"), (5, "50.0"), (6, "50.3")]
    )
    return f"""
    <html><head><title>{title}</title></head><body>
      <time>2026/06/30 09:30</time>
      <table><tr><th>统计期</th><th>PMI</th><th>生产</th><th>新订单</th></tr>{rows}</table>
    </body></html>
    """


def test_parse_nbs_pmi_table() -> None:
    publication = parse_nbs_pmi(_fixture_html())
    assert publication.published_at == datetime(2026, 6, 30, 9, 30)
    assert publication.records[-1].period == date(2026, 6, 1)
    assert publication.records[-1].value == Decimal("50.3")


def test_parser_fails_closed_on_wrong_title() -> None:
    with pytest.raises(ValueError, match="标题"):
        parse_nbs_pmi(_fixture_html("普通统计新闻 - 国家统计局"))


def test_parser_fails_closed_on_short_table() -> None:
    html = _fixture_html().replace("2026年6月", "无统计期").replace("2026年5月", "无统计期")
    with pytest.raises(ValueError, match="历史记录不足"):
        parse_nbs_pmi(html)
