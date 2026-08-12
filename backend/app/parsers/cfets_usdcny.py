from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation


PARSER_VERSION = "cfets-usdcny-json-v1"


@dataclass(frozen=True)
class CentralParityPoint:
    period: date
    value: Decimal


@dataclass(frozen=True)
class CentralParityHistory:
    points: tuple[CentralParityPoint, ...]
    start_date: date
    end_date: date


@dataclass(frozen=True)
class CentralParityLatest:
    period: date
    published_at: datetime
    value: Decimal


def _load(payload: bytes | str) -> dict:
    try:
        parsed = json.loads(payload)
    except (json.JSONDecodeError, UnicodeDecodeError, TypeError) as exc:
        raise ValueError("中国货币网返回内容不是有效JSON") from exc
    if not isinstance(parsed, dict) or parsed.get("head", {}).get("rep_code") != "200":
        raise ValueError("中国货币网返回状态异常")
    return parsed


def _decimal(value: object) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"USD/CNY中间价不是有效数字: {value}") from exc
    if not Decimal("4") <= result <= Decimal("10"):
        raise ValueError(f"USD/CNY中间价超出合理校验范围: {result}")
    return result


def parse_usdcny_history(payload: bytes | str) -> CentralParityHistory:
    root = _load(payload)
    data = root.get("data")
    records = root.get("records")
    if not isinstance(data, dict) or not isinstance(records, list) or not records:
        raise ValueError("中国货币网历史数据为空")
    if data.get("searchlist") != ["USD/CNY"] or data.get("currency") != "USD/CNY":
        raise ValueError("中国货币网历史查询并非USD/CNY单币种结果")
    try:
        start_date = date.fromisoformat(str(data["startDate"]))
        end_date = date.fromisoformat(str(data["endDate"]))
    except (KeyError, ValueError) as exc:
        raise ValueError("中国货币网历史查询区间缺失") from exc
    points: list[CentralParityPoint] = []
    seen: set[date] = set()
    for record in records:
        if not isinstance(record, dict) or not isinstance(record.get("values"), list):
            raise ValueError("中国货币网历史记录结构异常")
        try:
            period = date.fromisoformat(str(record["date"]))
        except (KeyError, ValueError) as exc:
            raise ValueError("中国货币网历史记录日期异常") from exc
        values = record["values"]
        if len(values) != 1 or period in seen or not start_date <= period <= end_date:
            raise ValueError("中国货币网USD/CNY历史记录未通过范围或唯一性校验")
        seen.add(period)
        points.append(CentralParityPoint(period=period, value=_decimal(values[0])))
    points.sort(key=lambda item: item.period)
    return CentralParityHistory(tuple(points), start_date, end_date)


def parse_usdcny_latest(payload: bytes | str) -> CentralParityLatest:
    root = _load(payload)
    data = root.get("data")
    records = root.get("records")
    if not isinstance(data, dict) or not isinstance(records, list):
        raise ValueError("中国货币网最新中间价结构异常")
    matches = [item for item in records if isinstance(item, dict) and item.get("vrtEName") == "USD/CNY"]
    if len(matches) != 1:
        raise ValueError("中国货币网最新数据缺少唯一USD/CNY记录")
    try:
        published_at = datetime.strptime(str(data["lastDate"]), "%Y-%m-%d %H:%M")
    except (KeyError, ValueError) as exc:
        raise ValueError("中国货币网最新数据发布时间异常") from exc
    return CentralParityLatest(
        period=published_at.date(),
        published_at=published_at,
        value=_decimal(matches[0].get("price")),
    )
