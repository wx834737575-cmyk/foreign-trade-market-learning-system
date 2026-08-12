from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


PARSER_VERSION = "nbs-core-monthly-release-v1"


@dataclass(frozen=True)
class ReleaseIndex:
    urls: dict[str, str]


@dataclass(frozen=True)
class ReleaseValue:
    dataset_code: str
    value: Decimal


@dataclass(frozen=True)
class CoreMonthlyPublication:
    kind: str
    title: str
    period: date
    published_at: datetime
    values: tuple[ReleaseValue, ...]


_TITLE_MARKERS = {
    "cpi": "居民消费价格",
    "ppi": "工业生产者出厂价格",
    "industrial": "规模以上工业增加值",
    "retail": "社会消费品零售总额",
}
_PUBLISHED_RE = re.compile(r"(20\d{2})[/-](\d{1,2})[/-](\d{1,2})\s+(\d{1,2}):(\d{2})")


def _compact(value: str) -> str:
    return re.sub(r"\s+", "", value).replace("％", "%")


def _decimal(value: str) -> Decimal:
    try:
        return Decimal(value.replace(",", ""))
    except InvalidOperation as exc:
        raise ValueError(f"国家统计局月度指标不是有效数字: {value}") from exc


def _signed(direction: str, value: str) -> Decimal:
    number = _decimal(value)
    if direction in {"下降", "减少"}:
        return -number
    if direction == "持平":
        return Decimal("0")
    return number


def parse_release_index(html: bytes | str, base_url: str) -> ReleaseIndex:
    soup = BeautifulSoup(html, "lxml")
    found: dict[str, list[str]] = {kind: [] for kind in _TITLE_MARKERS}
    for link in soup.select("a[href]"):
        title = _compact(link.get_text(" ", strip=True))
        url = urljoin(base_url, link.get("href"))
        if urlparse(url).hostname != "www.stats.gov.cn":
            continue
        for kind, marker in _TITLE_MARKERS.items():
            if marker in title and url not in found[kind]:
                found[kind].append(url)
    missing = [kind for kind, urls in found.items() if not urls]
    if missing:
        raise ValueError(f"国家统计局数据发布页缺少核心月度入口: {', '.join(missing)}")
    return ReleaseIndex({kind: urls[0] for kind, urls in found.items()})


def _publication_context(html: bytes | str, expected_marker: str) -> tuple[str, str, datetime]:
    soup = BeautifulSoup(html, "lxml")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    if expected_marker not in _compact(title) or "国家统计局" not in title:
        raise ValueError(f"国家统计局发布页标题不符合预期: {expected_marker}")
    text = soup.get_text(" ", strip=True)
    published = _PUBLISHED_RE.search(text)
    if published is None:
        raise ValueError("国家统计局发布页缺少官方发布时间")
    return title, _compact(text), datetime(*(int(part) for part in published.groups()))


def _period_from_title(title: str) -> date:
    match = re.search(r"(20\d{2})年(\d{1,2})月份", _compact(title))
    if match is None:
        raise ValueError("国家统计局发布页标题缺少统计月份")
    return date(int(match.group(1)), int(match.group(2)), 1)


def parse_cpi_release(html: bytes | str) -> CoreMonthlyPublication:
    title, text, published_at = _publication_context(html, _TITLE_MARKERS["cpi"])
    period = _period_from_title(title)
    yoy = re.search(r"全国居民消费价格同比(上涨|下降|持平)([\d.]+)%", text)
    mom = re.search(r"全国居民消费价格环比(上涨|下降|持平)([\d.]+)%", text)
    title_yoy = re.search(r"居民消费价格同比(上涨|下降|持平)([\d.]+)%", _compact(title))
    if yoy is None or mom is None or title_yoy is None:
        raise ValueError("国家统计局CPI发布页缺少同比或环比")
    yoy_value = _signed(*yoy.groups())
    mom_value = _signed(*mom.groups())
    if yoy_value != _signed(*title_yoy.groups()) or not -Decimal("20") <= yoy_value <= Decimal("20") or not -Decimal("20") <= mom_value <= Decimal("20"):
        raise ValueError("国家统计局CPI标题与正文未通过交叉校验")
    return CoreMonthlyPublication(
        "cpi", title, period, published_at,
        (ReleaseValue("CN_CPI_YOY", yoy_value), ReleaseValue("CN_CPI_MOM", mom_value)),
    )


def parse_ppi_release(html: bytes | str) -> CoreMonthlyPublication:
    title, text, published_at = _publication_context(html, _TITLE_MARKERS["ppi"])
    period = _period_from_title(title)
    values = re.search(r"全国工业生产者出厂价格同比(上涨|下降|持平)([\d.]+)%，环比(上涨|下降|持平)([\d.]+)%", text)
    title_values = re.search(r"工业生产者出厂价格同比(上涨|下降|持平)([\d.]+)%环比(上涨|下降|持平)([\d.]+)%", _compact(title))
    if values is None or title_values is None:
        raise ValueError("国家统计局PPI发布页缺少同比或环比")
    yoy_value = _signed(values.group(1), values.group(2))
    mom_value = _signed(values.group(3), values.group(4))
    if (yoy_value, mom_value) != (
        _signed(title_values.group(1), title_values.group(2)),
        _signed(title_values.group(3), title_values.group(4)),
    ) or not -Decimal("30") <= yoy_value <= Decimal("30") or not -Decimal("30") <= mom_value <= Decimal("30"):
        raise ValueError("国家统计局PPI标题与正文未通过交叉校验")
    return CoreMonthlyPublication(
        "ppi", title, period, published_at,
        (ReleaseValue("CN_PPI_YOY", yoy_value), ReleaseValue("CN_PPI_MOM", mom_value)),
    )


def parse_industrial_release(html: bytes | str) -> CoreMonthlyPublication:
    title, text, published_at = _publication_context(html, _TITLE_MARKERS["industrial"])
    period = _period_from_title(title)
    body = re.search(r"规模以上工业增加值同比实际(增长|下降|持平)([\d.]+)%", text)
    title_value = re.search(r"规模以上工业增加值(增长|下降|持平)([\d.]+)%", _compact(title))
    if body is None or title_value is None:
        raise ValueError("国家统计局工业增加值发布页缺少同比增速")
    value = _signed(*body.groups())
    if value != _signed(*title_value.groups()) or not -Decimal("30") <= value <= Decimal("30"):
        raise ValueError("国家统计局工业增加值标题与正文未通过交叉校验")
    return CoreMonthlyPublication(
        "industrial", title, period, published_at,
        (ReleaseValue("CN_INDUSTRIAL_VALUE_ADDED_YOY", value),),
    )


def parse_retail_release(html: bytes | str) -> CoreMonthlyPublication:
    title, text, published_at = _publication_context(html, _TITLE_MARKERS["retail"])
    year_match = re.search(r"(20\d{2})年", _compact(title))
    matches = re.findall(r"(\d{1,2})月份，社会消费品零售总额([\d,]+)亿元，同比(增长|下降|持平)([\d.]+)%", text)
    if year_match is None or not matches:
        raise ValueError("国家统计局社会消费品零售总额发布页缺少月度值")
    month, amount_text, direction, yoy_text = matches[0]
    comparable = {(item[0], item[1].replace(",", ""), item[2], item[3]) for item in matches}
    if len(comparable) != 1:
        raise ValueError("国家统计局社会消费品零售总额正文与表格不一致")
    amount = _decimal(amount_text)
    yoy_value = _signed(direction, yoy_text)
    if not Decimal("1000") <= amount <= Decimal("1000000") or not -Decimal("30") <= yoy_value <= Decimal("30"):
        raise ValueError("国家统计局社会消费品零售总额超出合理校验范围")
    period = date(int(year_match.group(1)), int(month), 1)
    return CoreMonthlyPublication(
        "retail", title, period, published_at,
        (
            ReleaseValue("CN_RETAIL_SALES_VALUE", amount),
            ReleaseValue("CN_RETAIL_SALES_YOY", yoy_value),
        ),
    )


PARSERS = {
    "cpi": parse_cpi_release,
    "ppi": parse_ppi_release,
    "industrial": parse_industrial_release,
    "retail": parse_retail_release,
}
