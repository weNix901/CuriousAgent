import pytest
from core.providers.serper_provider import SerperProvider


def test_serper_provider_name():
    provider = SerperProvider()
    assert provider.name == "serper"


@pytest.mark.asyncio
async def test_serper_search_no_api_key():
    provider = SerperProvider(api_key="")
    result = await provider.search("test query")
    assert result["result_count"] == 0
    assert result["results"] == []
