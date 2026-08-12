import pytest

from app.ingestion.customs_official_export import _validate_metadata


def test_customs_query_metadata_is_normalized() -> None:
    result = _validate_metadata(
        {
            "start_period": "2026-01-01",
            "end_period": "2026-06-01",
            "trade_flow": "出口",
            "currency": "美元",
            "product_codes": ["89079000"],
        }
    )
    assert result["source_url"] == "https://stats.customs.gov.cn/"
    assert result["product_codes"] == ["89079000"]


def test_customs_query_metadata_requires_full_scope() -> None:
    with pytest.raises(ValueError, match="缺少字段"):
        _validate_metadata({"start_period": "2026-01-01", "end_period": "2026-06-01"})
