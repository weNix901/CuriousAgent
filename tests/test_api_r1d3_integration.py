import pytest
from unittest.mock import Mock, patch
import json


class TestR1D3APIEndpoints:
    def setup_method(self):
        from curious_api import app
        self.app = app
        self.client = app.test_client()

    def test_api_r1d3_confidence_success(self):
        with patch('core.api.r1d3_tools.R1D3ToolHandler') as MockHandler:
            mock_handler = Mock()
            mock_handler.curious_check_confidence.return_value = {
                "topic": "test",
                "confidence": 0.8,
                "level": "expert"
            }
            MockHandler.return_value = mock_handler
            
            response = self.client.get('/api/r1d3/confidence?topic=test')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["status"] == "ok"
            assert data["result"]["confidence"] == 0.8

    def test_api_r1d3_confidence_missing_topic(self):
        response = self.client.get('/api/r1d3/confidence')
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert "error" in data

    def test_api_r1d3_inject_success(self):
        with patch('core.api.r1d3_tools.R1D3ToolHandler') as MockHandler:
            mock_handler = Mock()
            mock_handler.curious_agent_inject.return_value = {
                "status": "success",
                "queue_position": 1
            }
            MockHandler.return_value = mock_handler
            
            response = self.client.post('/api/r1d3/inject',
                json={"topic": "test", "source": "r1d3"})
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["status"] == "ok"

    def test_api_r1d3_synthesize_success(self):
        with patch('core.insight_synthesizer.InsightSynthesizer') as MockSynth:
            from core.insight_synthesizer import Insight
            
            mock_insight = Insight(
                id="ins_001",
                topic="test",
                hypothesis="test hypothesis",
                type="causal",
                reasoning="test reasoning",
                confidence=0.8,
                supporting_snippets=["s1"],
                generated_by="test",
                timestamp="2024-01-01"
            )
            
            mock_synth = Mock()
            mock_synth.synthesize.return_value = [mock_insight]
            MockSynth.return_value = mock_synth
            
            response = self.client.post('/api/r1d3/synthesize',
                json={"topic": "test", "sub_topic_results": {"t1": []}})
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["status"] == "ok"
            assert data["insights_count"] == 1

    def test_api_r1d3_unshared_discoveries(self):
        with patch('core.sync.r1d3_sync.R1D3Sync') as MockSync:
            mock_sync = Mock()
            mock_sync.get_unshared_discoveries.return_value = [
                {"topic": "discovery1"}
            ]
            MockSync.return_value = mock_sync
            
            response = self.client.get('/api/r1d3/discoveries/unshared')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["status"] == "ok"
            assert data["count"] == 1
