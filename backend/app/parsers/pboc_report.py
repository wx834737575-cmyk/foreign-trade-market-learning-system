import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from bs4 import BeautifulSoup


@dataclass(frozen=True)
class MoneySupplyRecord:
    code: str
    balance_trillion: Decimal
    yoy_percent: Decimal


@dataclass(frozen=True)
class MoneySupplyPublication:
    title: str
    published_at: datetime
    records: tuple[MoneySupplyRecord, ...]


_PATTERNS = {
    "CN_M2": re.compile(r"广义货币\s*\(?M2\)?余额\s*([\d.]+)万亿元[，,]同比增长\s*([\-\d.]+)%"),
    "CN_M1": re.compile(r"狭义货币\s*\(?M1\)?余额\s*([\d.]+)万亿元[，,]同比增长\s*([\-\d.]+)%"),
    "CN_M0": re.compile(r"流通中货币\s*\(?M0\)?余额\s*([\d.]+)万亿元[，,]同比增长\s*([\-\d.]+)%"),
}


def parse_money_supply(text: str) -> list[MoneySupplyRecord]:
    normalized = re.sub(r"\s+", "", text).replace("％", "%").replace("－", "-")
    records: list[MoneySupplyRecord] = []
    for code, pattern in _PATTERNS.items():
        match = pattern.search(normalized)
        if match:
            records.append(
                MoneySupplyRecord(
                    code=code,
                    balance_trillion=Decimal(match.group(1)),
                    yoy_percent=Decimal(match.group(2)),
                )
            )
    if len(records) != 3:
        missing = sorted(set(_PATTERNS) - {item.code for item in records})
        raise ValueError(f"货币供应量字段不完整: {', '.join(missing)}")
    return records


def parse_money_supply_page(html: bytes | str) -> MoneySupplyPublication:
    soup = BeautifulSoup(html, "lxml")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    if "2026年上半年金融统计数据报告" not in title:
        raise ValueError("人民银行金融统计页面标题不符合预期")
    page_text = soup.get_text(" ", strip=True)
    published_match = re.search(r"(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2}):(\d{2})", page_text)
    if published_match is None:
        raise ValueError("未找到人民银行官方发布时间")
    published_at = datetime(*(int(part) for part in published_match.groups()))
    records = tuple(parse_money_supply(page_text))
    return MoneySupplyPublication(title=title, published_at=published_at, records=records)
