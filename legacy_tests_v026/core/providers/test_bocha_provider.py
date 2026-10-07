import pytest
from core.providers.bocha_provider import BochaSearchProvider


def test_bocha_provider_name():
    provider = BochaSearchProvider()
    assert provider.name == "bocha"


@pytest.mark.asyncio
async def test_bocha_search_no_api_key():
    provider = BochaSearchProvider(api_key="")
    result = await provider.search("test query")
    assert result["result_count"] == 0
    assert result["results"] == []
