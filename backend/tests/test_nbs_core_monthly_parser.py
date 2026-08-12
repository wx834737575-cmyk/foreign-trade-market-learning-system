from datetime import date, datetime
from decimal import Decimal

import pytest

from app.parsers.nbs_core_monthly import (
    parse_cpi_release,
    parse_industrial_release,
    parse_ppi_release,
    parse_release_index,
    parse_retail_release,
)


def _page(title: str, body: str) -> str:
    return f"<html><head><title>{title} - 国家统计局</title></head><body>2026/07/15 10:00 {body}</body></html>"


def test_release_index_finds_unique_official_pages() -> None:
    html = """
    <a href="./202607/cpi.html">2026年6月份居民消费价格同比上涨1.0%</a>
    <a href="./202607/ppi.html">2026年6月份工业生产者出厂价格同比上涨4.1%</a>
    <a href="./202607/industrial.html">2026年6月份规模以上工业增加值增长5.3%</a>
    <a href="./202607/retail.html">2026年上半年社会消费品零售总额增长1.3%</a>
    """
    result = parse_release_index(html, "https://www.stats.gov.cn/sj/zxfb/")
    assert result.urls["cpi"] == "https://www.stats.gov.cn/sj/zxfb/202607/cpi.html"
    assert set(result.urls) == {"cpi", "ppi", "industrial", "retail"}


def test_parse_cpi_and_ppi_releases() -> None:
    cpi = parse_cpi_release(
        _page(
            "2026年6月份居民消费价格同比上涨1.0%",
            "2026年6月份，全国居民消费价格同比上涨1.0%。6月份，全国居民消费价格环比下降0.3%。",
        )
    )
    ppi = parse_ppi_release(
        _page(
            "2026年6月份工业生产者出厂价格同比上涨4.1% 环比下降0.3%",
            "2026年6月份，全国工业生产者出厂价格同比上涨4.1%，环比下降0.3%。",
        )
    )
    assert cpi.period == date(2026, 6, 1)
    assert cpi.published_at == datetime(2026, 7, 15, 10, 0)
    assert {item.dataset_code: item.value for item in cpi.values} == {
        "CN_CPI_YOY": Decimal("1.0"),
        "CN_CPI_MOM": Decimal("-0.3"),
    }
    assert {item.dataset_code: item.value for item in ppi.values}["CN_PPI_YOY"] == Decimal("4.1")


def test_parse_industrial_and_retail_releases() -> None:
    industrial = parse_industrial_release(
        _page(
            "2026年6月份规模以上工业增加值增长5.3%",
            "6月份，规模以上工业增加值同比实际增长5.3%。",
        )
    )
    retail = parse_retail_release(
        _page(
            "2026年上半年社会消费品零售总额增长1.3%",
            "6月份，社会消费品零售总额42691亿元，同比增长1.0%。",
        )
    )
    assert industrial.values[0].value == Decimal("5.3")
    assert retail.period == date(2026, 6, 1)
    assert {item.dataset_code: item.value for item in retail.values} == {
        "CN_RETAIL_SALES_VALUE": Decimal("42691"),
        "CN_RETAIL_SALES_YOY": Decimal("1.0"),
    }


def test_cpi_rejects_title_body_mismatch() -> None:
    html = _page(
        "2026年6月份居民消费价格同比上涨1.1%",
        "2026年6月份，全国居民消费价格同比上涨1.0%。6月份，全国居民消费价格环比下降0.3%。",
    )
    with pytest.raises(ValueError, match="交叉校验"):
        parse_cpi_release(html)
