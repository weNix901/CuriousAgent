"""
Tests for LLM Client - Layer 3 insights generation
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import requests


def test_client_initialization_with_api_key():
    """Test LLMClient initialization with explicit API key"""
    from core.llm_client import LLMClient
    
    client = LLMClient(api_key='test-key')
    assert client.api_key == 'test-key'
    assert client.model == 'minimax-m2.7'
    assert client.timeout == 60


def test_client_initialization_from_env():
    """Test LLMClient reads API key from environment"""
    with patch.dict('os.environ', {'MINIMAX_API_KEY': 'env-test-key'}):
        from core.llm_client import LLMClient
        client = LLMClient()
        assert client.api_key == 'env-test-key'


def test_client_initialization_no_key():
    """Test LLMClient handles missing API key gracefully"""
    with patch.dict('os.environ', {}, clear=True):
        from core.llm_client import LLMClient
        client = LLMClient()
        assert client.api_key == ''


def test_generate_comparison_prompt():
    """Test prompt generation includes topic and paper info"""
    from core.llm_client import LLMClient
    
    client = LLMClient(api_key='test')
    
    papers = [
        {
            "title": "Paper 1 Title",
            "authors": ["Author A", "Author B"],
            "abstract": "This is the abstract of paper 1.",
            "key_findings": ["finding1", "finding2"],
            "relevance_score": 0.85
        },
        {
            "title": "Paper 2 Title",
            "authors": ["Author C"],
            "abstract": "This is the abstract of paper 2.",
            "key_findings": ["finding3"],
            "relevance_score": 0.72
        }
    ]
    
    prompt = client._generate_comparison_prompt("knowledge graph embedding", papers)
    
    assert "knowledge graph embedding" in prompt
    assert "Paper 1 Title" in prompt
    assert "Paper 2 Title" in prompt
    assert "finding1" in prompt
    assert "finding2" in prompt
    assert "finding3" in prompt


def test_generate_insights_returns_error_without_api_key():
    """Test generate_insights returns error when no API key configured"""
    from core.llm_client import LLMClient
    
    client = LLMClient(api_key='')
    
    result = client.generate_insights("test topic", [{"title": "Paper"}])
    
    assert result["status"] == "error"
    assert "MINIMAX_API_KEY" in result["error"]
    assert result["insights"] == ""


def test_generate_insights_skips_single_paper():
    """Test generate_insights skips when less than 2 papers"""
    from core.llm_client import LLMClient
    
    client = LLMClient(api_key='test-key')
    
    result = client.generate_insights("test topic", [{"title": "Only Paper"}])
    
    assert result["status"] == "skipped"
    assert "at least 2 papers" in result["reason"].lower()


def test_generate_insights_success():
    """Test successful insight generation"""
    from core.llm_client import LLMClient
    
    client = LLMClient(api_key='test-key')
    
    papers = [
        {"title": "Paper 1", "abstract": "Abstract 1", "key_findings": ["f1"]},
        {"title": "Paper 2", "abstract": "Abstract 2", "key_findings": ["f2"]}
    ]
    
    # Mock the _call_api method
    client._call_api = Mock(return_value="Generated insights about the papers")
    
    result = client.generate_insights("test topic", papers)
    
    assert result["status"] == "success"
    assert result["insights"] == "Generated insights about the papers"
    assert result["papers_compared"] == 2
    assert result["model"] == "minimax-m2.7"


def test_generate_insights_handles_api_error():
    """Test generate_insights handles API errors gracefully"""
    from core.llm_client import LLMClient
    
    client = LLMClient(api_key='test-key')
    
    papers = [
        {"title": "Paper 1", "abstract": "Abstract 1"},
        {"title": "Paper 2", "abstract": "Abstract 2"}
    ]
    
    # Mock the _call_api method to raise an exception
    client._call_api = Mock(side_effect=Exception("API connection failed"))
    
    result = client.generate_insights("test topic", papers)
    
    assert result["status"] == "error"
    assert "API connection failed" in result["error"]
    assert result["insights"] == ""


def test_call_api_makes_correct_request():
    """Test _call_api makes correct HTTP request to minimax API"""
    from core.llm_client import LLMClient
    
    client = LLMClient(api_key='test-api-key')
    
    mock_response = Mock()
    mock_response.json.return_value = {
        "choices": [
            {"message": {"content": "Test response from API"}}
        ]
    }
    mock_response.raise_for_status = Mock()
    
    with patch('requests.post', return_value=mock_response) as mock_post:
        result = client._call_api("Test prompt")
        
        # Verify request was made with correct parameters
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        
        assert call_args[1]['headers']['Authorization'] == 'Bearer test-api-key'
        assert call_args[1]['json']['model'] == 'minimax-m2.7'
        assert call_args[1]['json']['messages'][1]['content'] == 'Test prompt'
        assert call_args[1]['timeout'] == 60
        
        assert result == "Test response from API"


def test_call_api_handles_timeout():
    """Test _call_api handles timeout errors"""
    from core.llm_client import LLMClient
    
    client = LLMClient(api_key='test-key')
    
    with patch('requests.post', side_effect=requests.Timeout("Request timed out")):
        with pytest.raises(requests.Timeout):
            client._call_api("Test prompt")


def test_call_api_handles_http_error():
    """Test _call_api handles HTTP errors"""
    from core.llm_client import LLMClient
    
    client = LLMClient(api_key='test-key')
    
    mock_response = Mock()
    mock_response.raise_for_status.side_effect = requests.HTTPError("401 Unauthorized")
    
    with patch('requests.post', return_value=mock_response):
        with pytest.raises(requests.HTTPError):
            client._call_api("Test prompt")


def test_call_api_handles_empty_response():
    """Test _call_api handles empty/malformed API response"""
    from core.llm_client import LLMClient
    
    client = LLMClient(api_key='test-key')
    
    mock_response = Mock()
    mock_response.json.return_value = {}  # Empty response
    mock_response.raise_for_status = Mock()
    
    with patch('requests.post', return_value=mock_response):
        result = client._call_api("Test prompt")
        assert result == ""


def test_generate_comparison_prompt_structure():
    """Test that generated prompt has expected structure"""
    from core.llm_client import LLMClient
    
    client = LLMClient(api_key='test')
    
    papers = [
        {"title": "Test Paper", "authors": ["A"], "abstract": "Abstract", "key_findings": ["f1"], "relevance_score": 0.8}
    ]
    
    prompt = client._generate_comparison_prompt("AI agents", papers)
    
    # Check for expected sections in the prompt
    assert "研究主题" in prompt or "topic" in prompt.lower()
    assert "论文" in prompt or "paper" in prompt.lower()
    assert "方法论对比" in prompt or "method" in prompt.lower()
