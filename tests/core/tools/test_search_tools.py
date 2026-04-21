"""Tests for search_tools module - all external calls mocked."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, mock_open

MOCK_SEARCH_RESULTS = {
    "results": [
        {"title": "Test Result 1", "snippet": "Test snippet 1", "url": "https://example.com/1"},
        {"title": "Test Result 2", "snippet": "Test snippet 2", "url": "https://example.com/2"}
    ],
    "result_count": 2,
    "raw": {"query": "test query"}
}

MOCK_WEB_CONTENT = "<html><body><h1>Test Page</h1><p>Test content</p></body></html>"

MOCK_PDF_BYTES = b"%PDF-1.4\n% mock pdf content"


class TestSearchWebTool:
    @pytest.mark.asyncio
    async def test_search_web_returns_results(self):
        from core.tools.search_tools import SearchWebTool, SearchProviderRegistry
        
        mock_provider = AsyncMock()
        mock_provider.search = AsyncMock(return_value=MOCK_SEARCH_RESULTS)
        
        with patch.object(SearchProviderRegistry, 'get_primary_provider', return_value=mock_provider):
            with patch.object(SearchProviderRegistry, 'get_fallback_provider', return_value=None):
                tool = SearchWebTool()
                result = await tool.execute(query="test query")
                
                assert "Test Result 1" in result
                assert "https://example.com/1" in result

    @pytest.mark.asyncio
    async def test_search_web_uses_config_provider(self):
        from core.tools.search_tools import SearchWebTool, SearchProviderRegistry
        
        mock_provider = AsyncMock()
        mock_provider.search = AsyncMock(return_value=MOCK_SEARCH_RESULTS)
        
        with patch.object(SearchProviderRegistry, 'get_primary_provider', return_value=mock_provider):
            with patch.object(SearchProviderRegistry, 'get_fallback_provider', return_value=None):
                tool = SearchWebTool()
                await tool.execute(query="test query")
                
                mock_provider.search.assert_called()

    @pytest.mark.asyncio
    async def test_search_web_no_results(self):
        from core.tools.search_tools import SearchWebTool, SearchProviderRegistry
        
        mock_provider = AsyncMock()
        mock_provider.search = AsyncMock(return_value={"results": [], "result_count": 0, "raw": {}})
        
        with patch.object(SearchProviderRegistry, 'get_primary_provider', return_value=mock_provider):
            with patch.object(SearchProviderRegistry, 'get_fallback_provider', return_value=mock_provider):
                tool = SearchWebTool()
                result = await tool.execute(query="test query")
                
                assert "No results" in result or "0 results" in result

    @pytest.mark.asyncio
    async def test_search_web_provider_error(self):
        from core.tools.search_tools import SearchWebTool, SearchProviderRegistry
        
        mock_provider = AsyncMock()
        mock_provider.search = AsyncMock(side_effect=Exception("API Error"))
        
        with patch.object(SearchProviderRegistry, 'get_primary_provider', return_value=mock_provider):
            with patch.object(SearchProviderRegistry, 'get_fallback_provider', return_value=None):
                tool = SearchWebTool()
                result = await tool.execute(query="test query")
                
                assert "Error" in result

    @pytest.mark.asyncio
    async def test_search_web_fallback_provider(self):
        from core.tools.search_tools import SearchWebTool, SearchProviderRegistry
        
        primary = AsyncMock()
        primary.search = AsyncMock(return_value={"results": [], "result_count": 0, "raw": {}})
        
        secondary = AsyncMock()
        secondary.search = AsyncMock(return_value=MOCK_SEARCH_RESULTS)
        
        with patch.object(SearchProviderRegistry, 'get_primary_provider', return_value=primary):
            with patch.object(SearchProviderRegistry, 'get_fallback_provider', return_value=secondary):
                tool = SearchWebTool()
                result = await tool.execute(query="test query")
                
                assert "Test Result 1" in result

    def test_search_web_has_name(self):
        from core.tools.search_tools import SearchWebTool
        
        tool = SearchWebTool()
        assert tool.name == "search_web"

    def test_search_web_has_description(self):
        from core.tools.search_tools import SearchWebTool
        
        tool = SearchWebTool()
        assert "search" in tool.description.lower()

    def test_search_web_has_parameters(self):
        from core.tools.search_tools import SearchWebTool
        
        tool = SearchWebTool()
        params = tool.parameters
        
        assert params["type"] == "object"
        assert "query" in params["properties"]


class TestFetchPageTool:
    @pytest.mark.asyncio
    async def test_fetch_page_returns_content(self):
        from core.tools.search_tools import FetchPageTool
        
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value=MOCK_WEB_CONTENT)
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)
        
        mock_get = MagicMock(return_value=mock_response)
        
        mock_session = MagicMock()
        mock_session.get = mock_get
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        
        with patch('core.tools.search_tools.aiohttp.ClientSession', return_value=mock_session):
            tool = FetchPageTool()
            result = await tool.execute(url="https://example.com")
            
            assert "Test Page" in result or "Test content" in result

    @pytest.mark.asyncio
    async def test_fetch_page_uses_async_http(self):
        from core.tools.search_tools import FetchPageTool
        
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value=MOCK_WEB_CONTENT)
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)
        
        mock_get = MagicMock(return_value=mock_response)
        
        mock_session = MagicMock()
        mock_session.get = mock_get
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        
        with patch('core.tools.search_tools.aiohttp.ClientSession', return_value=mock_session):
            tool = FetchPageTool()
            await tool.execute(url="https://example.com")
            
            mock_get.assert_called()

    @pytest.mark.asyncio
    async def test_fetch_page_404_error(self):
        from core.tools.search_tools import FetchPageTool
        
        mock_response = AsyncMock()
        mock_response.status = 404
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)
        
        mock_get = MagicMock(return_value=mock_response)
        
        mock_session = MagicMock()
        mock_session.get = mock_get
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        
        with patch('core.tools.search_tools.aiohttp.ClientSession', return_value=mock_session):
            tool = FetchPageTool()
            result = await tool.execute(url="https://example.com/notfound")
            
            assert "Error" in result or "404" in result

    @pytest.mark.asyncio
    async def test_fetch_page_timeout(self):
        from core.tools.search_tools import FetchPageTool
        
        mock_session = MagicMock()
        mock_session.get = MagicMock(side_effect=Exception("Timeout"))
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        
        with patch('core.tools.search_tools.aiohttp.ClientSession', return_value=mock_session):
            tool = FetchPageTool()
            result = await tool.execute(url="https://example.com")
            
            assert "Error" in result

    @pytest.mark.asyncio
    async def test_fetch_page_strips_html(self):
        from core.tools.search_tools import FetchPageTool
        
        html_content = "<html><body><h1>Title</h1><p>Content</p></body></html>"
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value=html_content)
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)
        
        mock_get = MagicMock(return_value=mock_response)
        
        mock_session = MagicMock()
        mock_session.get = mock_get
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        
        with patch('core.tools.search_tools.aiohttp.ClientSession', return_value=mock_session):
            tool = FetchPageTool()
            result = await tool.execute(url="https://example.com")
            
            assert "Title" in result or "Content" in result

    def test_fetch_page_has_name(self):
        from core.tools.search_tools import FetchPageTool
        
        tool = FetchPageTool()
        assert tool.name == "fetch_page"

    def test_fetch_page_has_description(self):
        from core.tools.search_tools import FetchPageTool
        
        tool = FetchPageTool()
        assert "fetch" in tool.description.lower() or "webpage" in tool.description.lower()

    def test_fetch_page_has_parameters(self):
        from core.tools.search_tools import FetchPageTool
        
        tool = FetchPageTool()
        params = tool.parameters
        
        assert params["type"] == "object"
        assert "url" in params["properties"]


class TestDownloadPaperTool:
    @pytest.mark.asyncio
    async def test_download_paper_returns_pdf_bytes(self):
        from core.tools.search_tools import DownloadPaperTool
        
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.read = AsyncMock(return_value=MOCK_PDF_BYTES)
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)
        
        mock_get = MagicMock(return_value=mock_response)
        
        mock_session = MagicMock()
        mock_session.get = mock_get
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        
        with patch('core.tools.search_tools.aiohttp.ClientSession', return_value=mock_session):
            tool = DownloadPaperTool()
            result = await tool.execute(url="https://arxiv.org/pdf/test.pdf")
            
            assert "Downloaded" in result

    @pytest.mark.asyncio
    async def test_download_paper_saves_file(self):
        from core.tools.search_tools import DownloadPaperTool
        
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.read = AsyncMock(return_value=MOCK_PDF_BYTES)
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)
        
        mock_get = MagicMock(return_value=mock_response)
        
        mock_session = MagicMock()
        mock_session.get = mock_get
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        
        with patch('core.tools.search_tools.aiohttp.ClientSession', return_value=mock_session):
            with patch('builtins.open', mock_open()) as mock_file:
                tool = DownloadPaperTool()
                await tool.execute(url="https://arxiv.org/pdf/test.pdf", output_path="/tmp/test.pdf")
                
                mock_file.assert_called()

    @pytest.mark.asyncio
    async def test_download_paper_404_error(self):
        from core.tools.search_tools import DownloadPaperTool
        
        mock_response = AsyncMock()
        mock_response.status = 404
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)
        
        mock_get = MagicMock(return_value=mock_response)
        
        mock_session = MagicMock()
        mock_session.get = mock_get
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        
        with patch('core.tools.search_tools.aiohttp.ClientSession', return_value=mock_session):
            tool = DownloadPaperTool()
            result = await tool.execute(url="https://arxiv.org/pdf/notfound.pdf")
            
            assert "Error" in result or "404" in result

    @pytest.mark.asyncio
    async def test_download_paper_not_pdf(self):
        from core.tools.search_tools import DownloadPaperTool
        
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.headers = {"Content-Type": "text/html"}
        mock_response.read = AsyncMock(return_value=b"<html>not a pdf</html>")
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)
        
        mock_get = MagicMock(return_value=mock_response)
        
        mock_session = MagicMock()
        mock_session.get = mock_get
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        
        with patch('core.tools.search_tools.aiohttp.ClientSession', return_value=mock_session):
            tool = DownloadPaperTool()
            result = await tool.execute(url="https://example.com/notpdf")
            
            assert isinstance(result, str)

    def test_download_paper_has_name(self):
        from core.tools.search_tools import DownloadPaperTool
        
        tool = DownloadPaperTool()
        assert tool.name == "download_paper"

    def test_download_paper_has_description(self):
        from core.tools.search_tools import DownloadPaperTool
        
        tool = DownloadPaperTool()
        assert "download" in tool.description.lower() or "pdf" in tool.description.lower()

    def test_download_paper_has_parameters(self):
        from core.tools.search_tools import DownloadPaperTool
        
        tool = DownloadPaperTool()
        params = tool.parameters
        
        assert params["type"] == "object"
        assert "url" in params["properties"]


class TestParsePdfTool:
    @pytest.mark.asyncio
    async def test_parse_pdf_returns_text(self):
        from core.tools.search_tools import ParsePdfTool
        
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Extracted text from page"
        
        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
        mock_pdf.__exit__ = MagicMock(return_value=False)
        
        with patch('core.tools.search_tools.pdfplumber.open', return_value=mock_pdf):
            with patch('core.tools.search_tools.Path.exists', return_value=True):
                tool = ParsePdfTool()
                result = await tool.execute(pdf_path="/tmp/test.pdf")
                
                assert "Extracted text" in result

    @pytest.mark.asyncio
    async def test_parse_pdf_multiple_pages(self):
        from core.tools.search_tools import ParsePdfTool
        
        page1 = MagicMock()
        page1.extract_text.return_value = "Page 1 content"
        page2 = MagicMock()
        page2.extract_text.return_value = "Page 2 content"
        
        mock_pdf = MagicMock()
        mock_pdf.pages = [page1, page2]
        mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
        mock_pdf.__exit__ = MagicMock(return_value=False)
        
        with patch('core.tools.search_tools.pdfplumber.open', return_value=mock_pdf):
            with patch('core.tools.search_tools.Path.exists', return_value=True):
                tool = ParsePdfTool()
                result = await tool.execute(pdf_path="/tmp/test.pdf")
                
                assert "Page 1" in result
                assert "Page 2" in result

    @pytest.mark.asyncio
    async def test_parse_pdf_file_not_found(self):
        from core.tools.search_tools import ParsePdfTool
        
        with patch('core.tools.search_tools.pdfplumber.open', side_effect=FileNotFoundError()):
            tool = ParsePdfTool()
            result = await tool.execute(pdf_path="/tmp/notfound.pdf")
            
            assert "Error" in result or "not found" in result.lower()

    @pytest.mark.asyncio
    async def test_parse_pdf_invalid_pdf(self):
        from core.tools.search_tools import ParsePdfTool
        
        with patch('core.tools.search_tools.pdfplumber.open', side_effect=Exception("Invalid PDF")):
            tool = ParsePdfTool()
            result = await tool.execute(pdf_path="/tmp/invalid.pdf")
            
            assert "Error" in result

    @pytest.mark.asyncio
    async def test_parse_pdf_empty_pdf(self):
        from core.tools.search_tools import ParsePdfTool
        
        mock_page = MagicMock()
        mock_page.extract_text.return_value = ""
        
        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
        mock_pdf.__exit__ = MagicMock(return_value=False)
        
        with patch('core.tools.search_tools.pdfplumber.open', return_value=mock_pdf):
            tool = ParsePdfTool()
            result = await tool.execute(pdf_path="/tmp/empty.pdf")
            
            assert isinstance(result, str)

    def test_parse_pdf_has_name(self):
        from core.tools.search_tools import ParsePdfTool
        
        tool = ParsePdfTool()
        assert tool.name == "parse_pdf"

    def test_parse_pdf_has_description(self):
        from core.tools.search_tools import ParsePdfTool
        
        tool = ParsePdfTool()
        assert "parse" in tool.description.lower() or "pdf" in tool.description.lower()

    def test_parse_pdf_has_parameters(self):
        from core.tools.search_tools import ParsePdfTool
        
        tool = ParsePdfTool()
        params = tool.parameters
        
        assert params["type"] == "object"
        assert "pdf_path" in params["properties"]


class TestProcessPaperTool:
    @pytest.mark.asyncio
    async def test_process_paper_full_pipeline(self):
        from core.tools.search_tools import ProcessPaperTool
        
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.read = AsyncMock(return_value=MOCK_PDF_BYTES)
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)
        
        mock_get = MagicMock(return_value=mock_response)
        
        mock_session = MagicMock()
        mock_session.get = mock_get
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Paper content extracted"
        
        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
        mock_pdf.__exit__ = MagicMock(return_value=False)
        
        with patch('core.tools.search_tools.aiohttp.ClientSession', return_value=mock_session):
            with patch('core.tools.search_tools.pdfplumber.open', return_value=mock_pdf):
                with patch('core.tools.search_tools.os.makedirs'):
                    tool = ProcessPaperTool()
                    result = await tool.execute(url="https://arxiv.org/pdf/test.pdf", topic="test-paper")
                    
                    # New implementation returns JSON with paths and text_length
                    assert "pdf_path" in result or "text_length" in result

    @pytest.mark.asyncio
    async def test_process_paper_returns_metadata(self):
        from core.tools.search_tools import ProcessPaperTool
        
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.read = AsyncMock(return_value=MOCK_PDF_BYTES)
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)
        
        mock_get = MagicMock(return_value=mock_response)
        
        mock_session = MagicMock()
        mock_session.get = mock_get
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Content"
        
        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
        mock_pdf.__exit__ = MagicMock(return_value=False)
        
        with patch('core.tools.search_tools.aiohttp.ClientSession', return_value=mock_session):
            with patch('core.tools.search_tools.pdfplumber.open', return_value=mock_pdf):
                with patch('core.tools.search_tools.os.makedirs'):
                    tool = ProcessPaperTool()
                    result = await tool.execute(url="https://arxiv.org/pdf/test.pdf", topic="test-paper")
                    
                    assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_process_paper_download_fails(self):
        from core.tools.search_tools import ProcessPaperTool
        
        mock_session = MagicMock()
        mock_session.get = MagicMock(side_effect=Exception("Download failed"))
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        
        with patch('core.tools.search_tools.aiohttp.ClientSession', return_value=mock_session):
            with patch('core.tools.search_tools.os.makedirs'):
                tool = ProcessPaperTool()
                result = await tool.execute(url="https://arxiv.org/pdf/test.pdf", topic="test-paper")
                
                assert "Error" in result

    @pytest.mark.asyncio
    async def test_process_paper_parse_fails(self):
        from core.tools.search_tools import ProcessPaperTool
        
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.read = AsyncMock(return_value=MOCK_PDF_BYTES)
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)
        
        mock_get = MagicMock(return_value=mock_response)
        
        mock_session = MagicMock()
        mock_session.get = mock_get
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        
        with patch('core.tools.search_tools.aiohttp.ClientSession', return_value=mock_session):
            with patch('core.tools.search_tools.pdfplumber.open', side_effect=Exception("Parse failed")):
                with patch('core.tools.search_tools.os.makedirs'):
                    tool = ProcessPaperTool()
                    result = await tool.execute(url="https://arxiv.org/pdf/test.pdf", topic="test-paper")
                    
                    assert "Error" in result

    def test_process_paper_has_name(self):
        from core.tools.search_tools import ProcessPaperTool
        
        tool = ProcessPaperTool()
        assert tool.name == "process_paper"

    def test_process_paper_has_description(self):
        from core.tools.search_tools import ProcessPaperTool
        
        tool = ProcessPaperTool()
        assert "process" in tool.description.lower() or "paper" in tool.description.lower()

    def test_process_paper_has_parameters(self):
        from core.tools.search_tools import ProcessPaperTool
        
        tool = ProcessPaperTool()
        params = tool.parameters
        
        assert params["type"] == "object"
        assert "url" in params["properties"]
        assert "topic" in params["properties"]


class TestSearchToolsIntegration:
    """Integration tests for search tools."""

    def test_all_tools_inherit_from_base(self):
        from core.tools.search_tools import (
            SearchWebTool, FetchPageTool, DownloadPaperTool,
            ParsePdfTool, ProcessPaperTool
        )
        from core.tools.base import Tool
        
        tools = [SearchWebTool(), FetchPageTool(), DownloadPaperTool(),
                 ParsePdfTool(), ProcessPaperTool()]
        
        for tool in tools:
            assert isinstance(tool, Tool)

    def test_all_tools_have_unique_names(self):
        from core.tools.search_tools import (
            SearchWebTool, FetchPageTool, DownloadPaperTool,
            ParsePdfTool, ProcessPaperTool
        )
        
        tools = [SearchWebTool(), FetchPageTool(), DownloadPaperTool(),
                 ParsePdfTool(), ProcessPaperTool()]
        names = [tool.name for tool in tools]
        
        assert len(names) == len(set(names)), "Tool names must be unique"

    def test_all_tools_have_valid_schemas(self):
        from core.tools.search_tools import (
            SearchWebTool, FetchPageTool, DownloadPaperTool,
            ParsePdfTool, ProcessPaperTool
        )
        
        tools = [SearchWebTool(), FetchPageTool(), DownloadPaperTool(),
                 ParsePdfTool(), ProcessPaperTool()]
        
        for tool in tools:
            schema = tool.to_schema()
            assert schema["type"] == "function"
            assert "function" in schema
            assert "name" in schema["function"]
            assert "description" in schema["function"]
            assert "parameters" in schema["function"]
