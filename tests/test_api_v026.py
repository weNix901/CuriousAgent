"""Tests for v0.2.6 API routes (F13)."""
import pytest
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from curious_api import app


@pytest.fixture
def client():
    """Create test client"""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


class TestDreamInsightsAPI:
    """Test /api/kg/dream_insights endpoints."""
    
    def test_api_dream_insights_returns_list(self, client):
        """Should return list of dream insights."""
        response = client.get('/api/kg/dream_insights')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'insights' in data
        assert isinstance(data['insights'], list)
    
    def test_api_dream_insights_topic_filters(self, client):
        """Should filter insights by topic."""
        response = client.get('/api/kg/dream_insights/test_topic')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'insights' in data


class TestDormantNodesAPI:
    """Test /api/kg/dormant endpoint."""
    
    def test_api_dormant_returns_list(self, client):
        """Should return list of dormant nodes."""
        response = client.get('/api/kg/dormant')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'dormant_nodes' in data
        assert isinstance(data['dormant_nodes'], list)


class TestReactivateAPI:
    """Test /api/kg/reactivate endpoint."""
    
    def test_api_reactivate_requires_topic(self, client):
        """Should require topic parameter."""
        response = client.post('/api/kg/reactivate', 
                              json={})
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
    
    def test_api_reactivate_success(self, client):
        """Should reactivate dormant node."""
        response = client.post('/api/kg/reactivate',
                              json={"topic": "test_topic"})
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'ok'


class TestFrontierAPI:
    """Test /api/kg/frontier endpoint."""
    
    def test_api_frontier_returns_frontiers(self, client):
        """Should return knowledge frontier."""
        response = client.get('/api/kg/frontier')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'frontiers' in data
        assert isinstance(data['frontiers'], list)


class TestCalibrationAPI:
    """Test /api/kg/calibration endpoint."""
    
    def test_api_calibration_returns_error_and_verdict(self, client):
        """Should return calibration error and verdict."""
        response = client.get('/api/kg/calibration')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'calibration_error' in data
        assert 'verdict' in data
        assert data['verdict'] in ['well_calibrated', 'overconfident', 'moderate']


class TestConfidenceAPI:
    """Test /api/kg/confidence/<topic> endpoint."""
    
    def test_api_confidence_returns_interval(self, client):
        """Should return confidence interval for topic."""
        response = client.get('/api/kg/confidence/test_topic')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'topic' in data
        assert 'confidence_low' in data
        assert 'confidence_high' in data
        assert isinstance(data['confidence_low'], float)
        assert isinstance(data['confidence_high'], float)
