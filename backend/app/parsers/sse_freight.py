from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from bs4 import BeautifulSoup


PARSER_VERSION = "sse-latest-composite-html-v1"


@dataclass(frozen=True)
class FreightIndexPublication:
    index_code: str
    period: date
    previous_period: date
    value: Decimal
    previous_value: Decimal
    change: Decimal


def _decimal(value: str) -> Decimal:
    try:
        return Decimal(value.replace(",", ""))
    except InvalidOperation as exc:
        raise ValueError(f"航运指数数值异常: {value}") from exc


def parse_freight_index(payload: bytes | str, index_code: str) -> FreightIndexPublication:
    code = index_code.upper()
    if code not in {"SCFI", "CCFI"}:
        raise ValueError("仅支持SCFI或CCFI综合指数")
    text = payload.decode("utf-8") if isinstance(payload, bytes) else payload
    soup = BeautifulSoup(text, "lxml")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    if code not in title:
        raise ValueError(f"上海航运交易所页面标题不是{code}")
    publication_dates: list[date] = []
    for row in soup.select("tr"):
        row_text = row.get_text(" ", strip=True)
        if "上期" in row_text and "本期" in row_text:
            publication_dates = [date.fromisoformat(item) for item in re.findall(r"20\d{2}-\d{2}-\d{2}", row_text)]
            break
    if len(publication_dates) != 2 or publication_dates[0] >= publication_dates[1]:
        raise ValueError("上海航运交易所指数表头缺少有效的本期和上期日期")
    rows = []
    for row in soup.select("tr"):
        cells = [cell.get_text(" ", strip=True) for cell in row.select("th,td")]
        label = " ".join(cells)
        if "综合指数" in label or "Comprehensive Index" in label:
            rows.append(cells)
    if len(rows) != 1:
        raise ValueError(f"上海航运交易所页面缺少唯一{code}综合指数行")
    numbers = [_decimal(item) for item in re.findall(r"[-+]?\d[\d,]*(?:\.\d+)?", " ".join(rows[0]))]
    if len(numbers) < 3:
        raise ValueError(f"{code}综合指数行数值不足")
    previous_value, value, change = numbers[-3:]
    if not Decimal("100") <= value <= Decimal("10000"):
        raise ValueError(f"{code}综合指数超出合理校验范围: {value}")
    if code == "SCFI":
        calculated = (value - previous_value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if calculated != change.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP):
            raise ValueError("SCFI本期、上期与涨跌额不一致")
    else:
        calculated = ((value / previous_value - 1) * 100).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
        if calculated != change.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP):
            raise ValueError("CCFI本期、上期与涨跌幅不一致")
    return FreightIndexPublication(
        index_code=code,
        period=publication_dates[1],
        previous_period=publication_dates[0],
        value=value,
        previous_value=previous_value,
        change=change,
    )
