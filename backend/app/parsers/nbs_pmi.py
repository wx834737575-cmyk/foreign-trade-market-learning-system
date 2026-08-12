import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from bs4 import BeautifulSoup


PARSER_VERSION = "nbs-pmi-v1"


@dataclass(frozen=True)
class PmiRecord:
    period: date
    value: Decimal


@dataclass(frozen=True)
class PmiPublication:
    title: str
    published_at: datetime
    records: tuple[PmiRecord, ...]


_PERIOD_RE = re.compile(r"^(\d{4})年\s*(\d{1,2})月$")
_PUBLISHED_RE = re.compile(r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})\s+(\d{1,2}):(\d{2})")


def parse_nbs_pmi(html: bytes | str) -> PmiPublication:
    soup = BeautifulSoup(html, "lxml")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    if "中国采购经理指数运行情况" not in title:
        raise ValueError("国家统计局PMI页面标题不符合预期")

    page_text = soup.get_text(" ", strip=True).replace("％", "%")
    published_match = _PUBLISHED_RE.search(page_text)
    if published_match is None:
        raise ValueError("未找到官方发布时间")
    published_at = datetime(*(int(part) for part in published_match.groups()))

    records: list[PmiRecord] = []
    for table in soup.find_all("table"):
        table_text = table.get_text(" ", strip=True)
        if "PMI" not in table_text or "生产" not in table_text or "新订单" not in table_text:
            continue
        for row in table.find_all("tr"):
            cells = [cell.get_text(" ", strip=True) for cell in row.find_all(["th", "td"])]
            if len(cells) < 2:
                continue
            period_match = _PERIOD_RE.match(cells[0].replace(" ", ""))
            if period_match is None:
                continue
            try:
                value = Decimal(cells[1].replace("%", "").strip())
            except InvalidOperation as exc:
                raise ValueError(f"PMI数值无法解析: {cells[1]}") from exc
            if not Decimal("35") <= value <= Decimal("65"):
                raise ValueError(f"PMI数值超出合理校验范围: {value}")
            records.append(PmiRecord(date(int(period_match.group(1)), int(period_match.group(2)), 1), value))
        if records:
            break

    if len(records) < 6:
        raise ValueError("制造业PMI历史记录不足，页面结构可能已变化")
    if len({record.period for record in records}) != len(records):
        raise ValueError("制造业PMI统计期重复")
    return PmiPublication(title=title, published_at=published_at, records=tuple(records))
