import pytest
from unittest.mock import Mock, patch


class TestLLMClientCreativeDream:
    @pytest.fixture
    def mock_llm_client(self):
        from core.llm_client import LLMClient
        with patch('core.llm_manager.LLMManager') as mock_manager_class:
            mock_manager = Mock()
            mock_manager_class.get_instance.return_value = mock_manager
            client = LLMClient()
            client.manager = mock_manager
            yield client, mock_manager

    def test_creative_dream_success_with_insight(self, mock_llm_client):
        client, mock_manager = mock_llm_client
        mock_manager.chat.return_value = '''{
            "has_insight": true,
            "insight": "Music and mathematics share common patterns in rhythm and symmetry",
            "insight_type": "analogy",
            "surprise": 0.8,
            "novelty": 0.7,
            "trigger_topic": "topic1"
        }'''
        
        result = client.creative_dream("music theory", "mathematics")
        
        assert result["has_insight"] is True
        assert "music" in result["insight"].lower() and "math" in result["insight"].lower()
        assert result["insight_type"] == "analogy"
        assert 0.0 <= result["surprise"] <= 1.0
        assert 0.0 <= result["novelty"] <= 1.0
        assert result["trigger_topic"] in ["topic1", "topic2", "combination"]

    def test_creative_dream_success_without_insight(self, mock_llm_client):
        client, mock_manager = mock_llm_client
        mock_manager.chat.return_value = '''{
            "has_insight": false,
            "insight": "",
            "insight_type": "unknown",
            "surprise": 0.0,
            "novelty": 0.0,
            "trigger_topic": "combination"
        }'''
        
        result = client.creative_dream("topic A", "topic B")
        
        assert result["has_insight"] is False
        assert result["insight"] == ""
        assert result["insight_type"] == "unknown"

    def test_creative_dream_malformed_json(self, mock_llm_client):
        client, mock_manager = mock_llm_client
        mock_manager.chat.return_value = "This is not JSON at all"
        
        result = client.creative_dream("topic1", "topic2")
        
        assert result["has_insight"] is False
        assert result["insight"] == ""
        assert result["insight_type"] == "unknown"
        assert result["surprise"] == 0.0
        assert result["novelty"] == 0.0

    def test_creative_dream_llm_error(self, mock_llm_client):
        client, mock_manager = mock_llm_client
        mock_manager.chat.side_effect = Exception("LLM provider error")
        
        result = client.creative_dream("topic1", "topic2")
        
        assert result["has_insight"] is False
        assert result["insight"] == ""

    def test_creative_dream_partial_json(self, mock_llm_client):
        client, mock_manager = mock_llm_client
        mock_manager.chat.return_value = 'Some text before {"has_insight": true, "insight": "test"} and after'
        
        result = client.creative_dream("topic1", "topic2")
        
        assert result["has_insight"] is True
        assert result["insight"] == "test"

    def test_creative_dream_response_structure(self, mock_llm_client):
        client, mock_manager = mock_llm_client
        mock_manager.chat.return_value = '''{
            "has_insight": true,
            "insight": "Cross-domain connection found",
            "insight_type": "cross_domain",
            "surprise": 0.65,
            "novelty": 0.85,
            "trigger_topic": "topic2"
        }'''
        
        result = client.creative_dream("AI", "biology")
        
        assert isinstance(result, dict)
        assert "has_insight" in result
        assert "insight" in result
        assert "insight_type" in result
        assert "surprise" in result
        assert "novelty" in result
        assert "trigger_topic" in result
        assert result["insight_type"] in ["analogy", "cross_domain", "synthesis", "question", "unknown"]
        assert result["trigger_topic"] in ["topic1", "topic2", "combination"]

    def test_creative_dream_missing_fields_in_json(self, mock_llm_client):
        client, mock_manager = mock_llm_client
        mock_manager.chat.return_value = '{"has_insight": true}'
        
        result = client.creative_dream("topic1", "topic2")
        
        assert result["has_insight"] is True
        assert result["insight"] == ""
        assert result["insight_type"] == "unknown"
        assert result["surprise"] == 0.5
        assert result["novelty"] == 0.5
        assert result["trigger_topic"] == "combination"

    def test_creative_dream_calls_with_correct_params(self, mock_llm_client):
        client, mock_manager = mock_llm_client
        mock_manager.chat.return_value = '{"has_insight": false}'
        
        client.creative_dream("creativity", "neuroscience")
        
        call_kwargs = mock_manager.chat.call_args
        assert "creative" in call_kwargs[1].get("task_type", "")
        assert call_kwargs[1].get("temperature") == 0.9
