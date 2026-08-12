import json
from datetime import date, datetime
from decimal import Decimal

import pytest

from app.parsers.cfets_usdcny import parse_usdcny_history, parse_usdcny_latest


def test_parse_usdcny_history_and_latest() -> None:
    history = {
        "head": {"rep_code": "200"},
        "data": {
            "searchlist": ["USD/CNY"],
            "currency": "USD/CNY",
            "startDate": "2026-07-17",
            "endDate": "2026-07-20",
        },
        "records": [
            {"date": "2026-07-20", "values": ["6.7948"]},
            {"date": "2026-07-17", "values": ["6.7929"]},
        ],
    }
    latest = {
        "head": {"rep_code": "200"},
        "data": {"lastDate": "2026-07-20 09:15"},
        "records": [{"vrtEName": "USD/CNY", "price": "6.7948"}],
    }

    parsed_history = parse_usdcny_history(json.dumps(history))
    parsed_latest = parse_usdcny_latest(json.dumps(latest))

    assert [point.period for point in parsed_history.points] == [date(2026, 7, 17), date(2026, 7, 20)]
    assert parsed_history.points[-1].value == Decimal("6.7948")
    assert parsed_latest.published_at == datetime(2026, 7, 20, 9, 15)
    assert parsed_latest.value == Decimal("6.7948")


def test_history_rejects_non_usdcny_query() -> None:
    payload = {
        "head": {"rep_code": "200"},
        "data": {
            "searchlist": ["EUR/CNY"],
            "currency": "EUR/CNY",
            "startDate": "2026-07-20",
            "endDate": "2026-07-20",
        },
        "records": [{"date": "2026-07-20", "values": ["8.1"]}],
    }
    with pytest.raises(ValueError, match="USD/CNY"):
        parse_usdcny_history(json.dumps(payload))
