"""Tests for /api/knowledge/session/startup endpoint."""
import pytest
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from curious_api import app


@pytest.fixture
def client():
    """Create test client"""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


class TestSessionStartupAPI:
    """Test /api/knowledge/session/startup endpoint."""
    
    def test_api_returns_ok_status(self, client):
        """Should return ok status."""
        response = client.get('/api/knowledge/session/startup')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data.get('status') == 'ok'
    
    def test_api_returns_injection_content(self, client):
        """Should return injection_content string."""
        response = client.get('/api/knowledge/session/startup')
        data = json.loads(response.data)
        assert 'injection_content' in data
        assert isinstance(data['injection_content'], str)
        assert len(data['injection_content']) > 0
    
    def test_api_returns_metadata(self, client):
        """Should return metadata with nodes info."""
        response = client.get('/api/knowledge/session/startup')
        data = json.loads(response.data)
        assert 'metadata' in data
        assert 'nodes_count' in data['metadata']
        assert 'sections_enabled' in data['metadata']
    
    def test_injection_contains_cognitive_framework(self, client):
        """Should include cognitive framework."""
        response = client.get('/api/knowledge/session/startup')
        data = json.loads(response.data)
        content = data.get('injection_content', '')
        assert '[CA Cognitive Framework]' in content