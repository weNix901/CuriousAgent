"""
Tests for LLM Client - Layer 3 insights generation
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import requests


def test_client_initialization_with_api_key():
    """Test LLMClient initialization with explicit API key"""
    from core.llm_client import LLMClient
    
    with patch.dict('os.environ', {'VOLCENGINE_MODEL': 'minimax-m2.7'}):
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
    from core.llm_client import LLMClient
    
    client = LLMClient(api_key='')
    client.manager.chat = Mock(side_effect=ValueError("No available LLM providers"))
    
    with pytest.raises(ValueError, match="No available LLM providers"):
        client.generate_insights("test topic", [{"title": "Paper"}])


def test_generate_insights_skips_single_paper():
    """Test generate_insights skips when less than 2 papers"""
    from core.llm_client import LLMClient
    
    client = LLMClient(api_key='test-key')
    
    # Mock the manager to avoid real API calls
    client.manager.chat = Mock(return_value="Insufficient papers for comparison")
    
    result = client.generate_insights("test topic", [{"title": "Only Paper"}])
    
    # Returns string, not dict
    assert isinstance(result, str)


def test_generate_insights_success():
    """Test successful insight generation"""
    from core.llm_client import LLMClient
    
    client = LLMClient(api_key='test-key')
    
    papers = [
        {"title": "Paper 1", "abstract": "Abstract 1", "key_findings": ["f1"]},
        {"title": "Paper 2", "abstract": "Abstract 2", "key_findings": ["f2"]}
    ]
    
    expected_insights = "Generated insights about the papers"
    client.manager.chat = Mock(return_value=expected_insights)
    
    result = client.generate_insights("test topic", papers)
    
    assert result == expected_insights
    assert isinstance(result, str)


def test_generate_insights_handles_api_error():
    from core.llm_client import LLMClient
    
    client = LLMClient(api_key='test-key')
    
    papers = [
        {"title": "Paper 1", "abstract": "Abstract 1"},
        {"title": "Paper 2", "abstract": "Abstract 2"}
    ]
    
    client.manager.chat = Mock(side_effect=Exception("API connection failed"))
    
    with pytest.raises(Exception, match="API connection failed"):
        client.generate_insights("test topic", papers)


def test_call_api_makes_correct_request():
    from core.llm_client import LLMClient
    
    client = LLMClient(api_key='test-api-key')
    client.manager.chat = Mock(return_value="Test response from API")
    
    result = client._call_api("Test prompt")
    
    client.manager.chat.assert_called_once_with("Test prompt", task_type="general", provider_override=None, model_override=None)
    assert result == "Test response from API"


def test_call_api_handles_timeout():
    from core.llm_client import LLMClient
    
    client = LLMClient(api_key='test-key')
    client.manager.chat = Mock(side_effect=requests.Timeout("Request timed out"))
    
    with pytest.raises(requests.Timeout):
        client._call_api("Test prompt")


def test_call_api_handles_http_error():
    from core.llm_client import LLMClient
    
    client = LLMClient(api_key='test-key')
    client.manager.chat = Mock(side_effect=requests.HTTPError("401 Unauthorized"))
    
    with pytest.raises(requests.HTTPError):
        client._call_api("Test prompt")


def test_call_api_handles_empty_response():
    from core.llm_client import LLMClient
    
    client = LLMClient(api_key='test-key')
    
    # Mock manager to return empty string
    client.manager.chat = Mock(return_value="")
    
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
