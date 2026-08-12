import pytest

from app.parsers.pboc_report import parse_money_supply, parse_money_supply_page


def test_parse_money_supply_report() -> None:
    text = """
    6月末，广义货币(M2)余额356.71万亿元，同比增长8.0%；
    狭义货币(M1)余额118.48万亿元，同比增长4.0%；
    流通中货币(M0)余额14.74万亿元，同比增长11.8%。
    """
    rows = parse_money_supply(text)
    assert [row.code for row in rows] == ["CN_M2", "CN_M1", "CN_M0"]
    assert str(rows[0].balance_trillion) == "356.71"


def test_parser_fails_closed_when_page_changes() -> None:
    with pytest.raises(ValueError, match="字段不完整"):
        parse_money_supply("页面结构已变化，没有完整指标")


def test_parse_official_page_metadata() -> None:
    html = """
    <html><head><title>2026年上半年金融统计数据报告</title></head><body>
    文章来源：沟通交流 2026-07-15 15:00:09
    6月末，广义货币(M2)余额356.71万亿元,同比增长8%。
    狭义货币(M1)余额118.48万亿元,同比增长4%。
    流通中货币(M0)余额14.74万亿元,同比增长11.8%。
    </body></html>
    """
    publication = parse_money_supply_page(html)
    assert publication.published_at.isoformat() == "2026-07-15T15:00:09"
    assert len(publication.records) == 3
