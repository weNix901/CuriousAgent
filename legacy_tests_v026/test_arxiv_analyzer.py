"""Tests for ArxivAnalyzer - Layer 2 exploration"""
import pytest
import sys
import os
from unittest.mock import Mock, patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.arxiv_analyzer import ArxivAnalyzer


class TestArxivAnalyzerInitialization:
    """Test suite for ArxivAnalyzer initialization"""

    def test_analyzer_initialization(self):
        """Test ArxivAnalyzer can be initialized"""
        from core.arxiv_analyzer import ArxivAnalyzer
        analyzer = ArxivAnalyzer()
        assert analyzer is not None

    def test_analyzer_has_relevance_threshold(self):
        """Test analyzer has default relevance threshold"""
        from core.arxiv_analyzer import ArxivAnalyzer
        analyzer = ArxivAnalyzer()
        assert hasattr(analyzer, 'relevance_threshold')
        assert 0 <= analyzer.relevance_threshold <= 1


class TestExtractArxivId:
    """Test suite for _extract_arxiv_id method"""

    def test_extract_arxiv_id_from_abs_url(self):
        """Test extracting arxiv ID from abs URL format"""
        from core.arxiv_analyzer import ArxivAnalyzer
        analyzer = ArxivAnalyzer()
        
        assert analyzer._extract_arxiv_id("https://arxiv.org/abs/2401.02009") == "2401.02009"

    def test_extract_arxiv_id_from_pdf_url(self):
        """Test extracting arxiv ID from PDF URL format"""
        from core.arxiv_analyzer import ArxivAnalyzer
        analyzer = ArxivAnalyzer()
        
        assert analyzer._extract_arxiv_id("https://arxiv.org/pdf/2401.02009.pdf") == "2401.02009"

    def test_extract_arxiv_id_from_short_format(self):
        """Test extracting arxiv ID from short format"""
        from core.arxiv_analyzer import ArxivAnalyzer
        analyzer = ArxivAnalyzer()
        
        assert analyzer._extract_arxiv_id("arxiv:2401.02009") == "2401.02009"

    def test_extract_arxiv_id_returns_none_for_invalid_url(self):
        """Test that invalid URL returns None"""
        from core.arxiv_analyzer import ArxivAnalyzer
        analyzer = ArxivAnalyzer()
        
        assert analyzer._extract_arxiv_id("not-an-arxiv-url") is None
        assert analyzer._extract_arxiv_id("https://example.com/paper") is None

    def test_extract_arxiv_id_with_new_format(self):
        """Test extracting arxiv ID with new format (e.g., 2301.12345)"""
        from core.arxiv_analyzer import ArxivAnalyzer
        analyzer = ArxivAnalyzer()
        
        assert analyzer._extract_arxiv_id("https://arxiv.org/abs/2301.12345") == "2301.12345"


class TestComputeRelevance:
    """Test suite for compute_relevance method"""

    def test_compute_relevance_returns_float(self):
        """Test that compute_relevance returns a float between 0 and 1"""
        from core.arxiv_analyzer import ArxivAnalyzer
        analyzer = ArxivAnalyzer()
        
        paper = {
            "title": "Knowledge Graph Embedding for AI",
            "abstract": "This paper explores graph neural networks..."
        }
        
        score = analyzer.compute_relevance("knowledge graph embedding", paper)
        assert isinstance(score, float)
        assert 0 <= score <= 1

    def test_compute_relevance_high_for_matching_topic(self):
        """Test high relevance score for matching topic"""
        from core.arxiv_analyzer import ArxivAnalyzer
        analyzer = ArxivAnalyzer()
        
        paper = {
            "title": "Knowledge Graph Embedding for AI",
            "abstract": "This paper explores graph neural networks for knowledge graphs..."
        }
        
        score = analyzer.compute_relevance("knowledge graph embedding", paper)
        assert score > 0.5  # Should be highly relevant

    def test_compute_relevance_low_for_unrelated_topic(self):
        """Test low relevance score for unrelated topic"""
        from core.arxiv_analyzer import ArxivAnalyzer
        analyzer = ArxivAnalyzer()
        
        paper = {
            "title": "Quantum Computing Algorithms",
            "abstract": "This paper explores quantum entanglement..."
        }
        
        score = analyzer.compute_relevance("knowledge graph embedding", paper)
        assert score < 0.5  # Should be low relevance

    def test_compute_relevance_empty_topic(self):
        """Test relevance with empty topic returns 0"""
        from core.arxiv_analyzer import ArxivAnalyzer
        analyzer = ArxivAnalyzer()
        
        paper = {
            "title": "Knowledge Graph Embedding for AI",
            "abstract": "This paper explores graph neural networks..."
        }
        
        score = analyzer.compute_relevance("", paper)
        assert score == 0.0


class TestFetchArxivMetadata:
    """Test suite for _fetch_arxiv_metadata method"""

    @patch('core.arxiv_analyzer.arxiv')
    def test_fetch_arxiv_metadata_returns_dict(self, mock_arxiv):
        """Test that _fetch_arxiv_metadata returns a dict with expected keys"""
        from core.arxiv_analyzer import ArxivAnalyzer
        analyzer = ArxivAnalyzer()
        
        # Mock the arxiv client
        mock_client = MagicMock()
        mock_paper = MagicMock()
        mock_paper.title = "Test Paper"
        mock_paper.summary = "Test abstract"
        mock_paper.published = "2024-01-01"
        mock_paper.primary_category = "cs.AI"
        mock_paper.pdf_url = "https://arxiv.org/pdf/2401.02009.pdf"
        mock_paper.authors = [MagicMock(__str__=lambda self: "Author Name")]
        
        mock_client.results.return_value = iter([mock_paper])
        mock_arxiv.Client.return_value = mock_client
        mock_arxiv.Search.return_value = MagicMock()
        
        result = analyzer._fetch_arxiv_metadata("2401.02009")
        
        assert result is not None
        assert "title" in result
        assert "abstract" in result
        assert "authors" in result

    @patch('core.arxiv_analyzer.arxiv')
    def test_fetch_arxiv_metadata_returns_none_on_error(self, mock_arxiv):
        """Test that _fetch_arxiv_metadata returns None on error"""
        from core.arxiv_analyzer import ArxivAnalyzer
        analyzer = ArxivAnalyzer()
        
        mock_arxiv.Client.side_effect = Exception("API Error")
        
        result = analyzer._fetch_arxiv_metadata("2401.02009")
        assert result is None


class TestAnalyzePapers:
    """Test suite for analyze_papers method"""

    @patch.object(ArxivAnalyzer, '_fetch_arxiv_metadata')
    def test_analyze_papers_returns_dict(self, mock_fetch):
        """Test that analyze_papers returns a dict with expected structure"""
        from core.arxiv_analyzer import ArxivAnalyzer
        analyzer = ArxivAnalyzer()
        
        mock_fetch.return_value = {
            "title": "Test Paper",
            "abstract": "Test abstract",
            "authors": ["Author"],
            "published": "2024-01-01",
            "primary_category": "cs.AI"
        }
        
        result = analyzer.analyze_papers("test topic", ["https://arxiv.org/abs/2401.02009"])
        
        assert isinstance(result, dict)
        assert "papers_analyzed" in result
        assert "papers" in result
        assert "high_relevance_count" in result

    @patch.object(ArxivAnalyzer, '_fetch_arxiv_metadata')
    def test_analyze_papers_limits_to_five(self, mock_fetch):
        """Test that analyze_papers limits analysis to 5 papers"""
        from core.arxiv_analyzer import ArxivAnalyzer
        analyzer = ArxivAnalyzer()
        
        mock_fetch.return_value = {
            "title": "Test Paper",
            "abstract": "Test abstract",
            "authors": ["Author"],
            "published": "2024-01-01",
            "primary_category": "cs.AI"
        }
        
        links = [
            "https://arxiv.org/abs/2401.02009",
            "https://arxiv.org/abs/2401.02010",
            "https://arxiv.org/abs/2401.02011",
            "https://arxiv.org/abs/2401.02012",
            "https://arxiv.org/abs/2401.02013",
            "https://arxiv.org/abs/2401.02014",
            "https://arxiv.org/abs/2401.02015"
        ]
        
        result = analyzer.analyze_papers("test topic", links)
        
        assert result["papers_analyzed"] <= 5

    def test_analyze_papers_handles_empty_list(self):
        """Test that analyze_papers handles empty list"""
        from core.arxiv_analyzer import ArxivAnalyzer
        analyzer = ArxivAnalyzer()
        
        result = analyzer.analyze_papers("test topic", [])
        
        assert result["papers_analyzed"] == 0
        assert result["papers"] == []


class TestDownloadAndExtract:
    """Test suite for _download_and_extract method"""

    @patch('core.arxiv_analyzer.requests.get')
    @patch.object(ArxivAnalyzer, '_extract_pdf_text')
    def test_download_and_extract_returns_text(self, mock_extract, mock_get):
        """Test that _download_and_extract returns extracted text"""
        from core.arxiv_analyzer import ArxivAnalyzer
        analyzer = ArxivAnalyzer()
        
        mock_response = MagicMock()
        mock_response.content = b"fake pdf content"
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response
        
        mock_extract.return_value = "Extracted text from PDF"
        
        result = analyzer._download_and_extract("2401.02009")
        
        assert result == "Extracted text from PDF"

    @patch('core.arxiv_analyzer.requests.get')
    def test_download_and_extract_returns_none_on_error(self, mock_get):
        """Test that _download_and_extract returns None on error"""
        from core.arxiv_analyzer import ArxivAnalyzer
        analyzer = ArxivAnalyzer()
        
        mock_get.side_effect = Exception("Network error")
        
        result = analyzer._download_and_extract("2401.02009")
        
        assert result is None


class TestExtractPdfText:
    """Test suite for _extract_pdf_text method"""

    @patch('core.arxiv_analyzer.PdfReader')
    def test_extract_pdf_text_returns_text(self, mock_pdf_reader):
        """Test that _extract_pdf_text extracts text from PDF"""
        analyzer = ArxivAnalyzer()
        
        mock_reader = MagicMock()
        mock_page1 = MagicMock()
        mock_page1.extract_text.return_value = "Page 1 text"
        mock_page2 = MagicMock()
        mock_page2.extract_text.return_value = "Page 2 text"
        mock_reader.pages = [mock_page1, mock_page2]
        
        mock_pdf_reader.return_value = mock_reader
        
        result = analyzer._extract_pdf_text("/fake/path.pdf", pages=2)
        
        assert "Page 1 text" in result
        assert "Page 2 text" in result

    def test_extract_pdf_text_returns_none_on_error(self):
        """Test that _extract_pdf_text returns None on error"""
        from core.arxiv_analyzer import ArxivAnalyzer
        analyzer = ArxivAnalyzer()
        
        result = analyzer._extract_pdf_text("/nonexistent/path.pdf", pages=2)
        
        assert result is None


class TestExtractKeyFindings:
    """Test suite for _extract_key_findings method"""

    def test_extract_key_findings_returns_list(self):
        """Test that _extract_key_findings returns a list"""
        from core.arxiv_analyzer import ArxivAnalyzer
        analyzer = ArxivAnalyzer()
        
        text = "We propose a new method for knowledge graphs. Our contribution is significant. The result shows improvement."
        
        findings = analyzer._extract_key_findings(text)
        
        assert isinstance(findings, list)

    def test_extract_key_findings_finds_keywords(self):
        """Test that _extract_key_findings finds sentences with keywords"""
        from core.arxiv_analyzer import ArxivAnalyzer
        analyzer = ArxivAnalyzer()
        
        text = "We propose a new method for knowledge graphs. Our contribution is significant. The result shows improvement. We conclude that this works."
        
        findings = analyzer._extract_key_findings(text)
        
        # Should find sentences with keywords like propose, contribution, result, conclusion
        assert len(findings) > 0

    def test_extract_key_findings_limits_to_three(self):
        """Test that _extract_key_findings limits to 3 findings"""
        from core.arxiv_analyzer import ArxivAnalyzer
        analyzer = ArxivAnalyzer()
        
        text = "We propose method 1. We propose method 2. We propose method 3. We propose method 4. We propose method 5."
        
        findings = analyzer._extract_key_findings(text)
        
        assert len(findings) <= 3
