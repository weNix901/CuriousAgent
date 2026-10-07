"""Tests for /api/knowledge/* endpoints."""

import pytest
import sys
import os

sys.path.insert(0, '/root/dev/curious-agent')

from curious_api import app


@pytest.fixture
def client():
    """Create test client."""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


class TestKnowledgeCheckEndpoint:
    """Test POST /api/knowledge/check endpoint."""

    def test_check_returns_confidence(self, client):
        """Check should return confidence level for topic."""
        response = client.post('/api/knowledge/check',
            json={'topic': 'FlashAttention'},
            content_type='application/json'
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] == True
        assert 'confidence' in data['result']
        assert 'level' in data['result']
        assert 'guidance' in data['result']

    def test_check_requires_topic(self, client):
        """Check should fail without topic."""
        response = client.post('/api/knowledge/check',
            json={},
            content_type='application/json'
        )
        
        assert response.status_code == 400

    def test_check_returns_gaps(self, client):
        """Check should return knowledge gaps."""
        response = client.post('/api/knowledge/check',
            json={'topic': 'UnknownTopic123'},
            content_type='application/json'
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert 'gaps' in data['result']


class TestKnowledgeLearnEndpoint:
    """Test POST /api/knowledge/learn endpoint."""

    def test_learn_injects_topic(self, client):
        """Learn should inject topic to queue."""
        response = client.post('/api/knowledge/learn',
            json={'topic': 'TestTopic', 'strategy': 'llm_answer'},
            content_type='application/json'
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] == True
        assert 'queue_id' in data['result']

    def test_learn_requires_topic(self, client):
        """Learn should fail without topic."""
        response = client.post('/api/knowledge/learn',
            json={'strategy': 'llm_answer'},
            content_type='application/json'
        )
        
        assert response.status_code == 400


class TestKnowledgeAnalyticsEndpoint:
    """Test GET /api/knowledge/analytics endpoint."""

    def test_analytics_returns_stats(self, client):
        """Analytics should return interaction statistics."""
        response = client.get('/api/knowledge/analytics')
        
        assert response.status_code == 200
        data = response.get_json()
        assert 'kg_hits' in data
        assert 'search_hits' in data
        assert 'llm_fallbacks' in data
        assert 'topics_learned' in data


class TestKnowledgeRecordEndpoint:
    """Test POST /api/knowledge/record endpoint."""

    def test_record_saves_to_kg(self, client):
        """Record should save search results to KG."""
        response = client.post('/api/knowledge/record',
            json={
                'topic': 'TestTopic',
                'content': 'Test content about the topic',
                'sources': ['https://example.com']
            },
            content_type='application/json'
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] == True

    def test_record_requires_topic(self, client):
        """Record should fail without topic."""
        response = client.post('/api/knowledge/record',
            json={'content': 'test'},
            content_type='application/json'
        )
        
        assert response.status_code == 400
