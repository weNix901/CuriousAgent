"""Tests for /api/curious/trigger endpoint"""
import pytest
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


class TestTriggerEndpoint:
    """Test suite for trigger endpoint"""

    def test_trigger_endpoint_accepts_post_request(self, client):
        """Test trigger endpoint accepts POST request with valid data"""
        response = client.post('/api/curious/trigger',
                              json={"topic": "test topic", "depth": "shallow"})
        
        assert response.status_code == 202
        data = response.get_json()
        assert data["status"] == "accepted"
        assert data["topic"] == "test topic"
        assert data["depth"] == "shallow"

    def test_trigger_endpoint_default_depth_is_medium(self, client):
        """Test that default depth is 'medium' when not specified"""
        response = client.post('/api/curious/trigger',
                              json={"topic": "test topic"})
        
        assert response.status_code == 202
        data = response.get_json()
        assert data["depth"] == "medium"

    def test_trigger_validates_depth_parameter(self, client):
        """Test trigger validates depth parameter"""
        response = client.post('/api/curious/trigger',
                              json={"topic": "test", "depth": "invalid"})
        
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data
        assert "invalid depth" in data["error"].lower()

    def test_trigger_requires_topic(self, client):
        """Test trigger requires topic parameter"""
        response = client.post('/api/curious/trigger',
                              json={"depth": "shallow"})
        
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data
        assert "topic" in data["error"].lower()

    def test_trigger_returns_estimated_time(self, client):
        """Test trigger returns estimated time based on depth"""
        # Test shallow
        response = client.post('/api/curious/trigger',
                              json={"topic": "test", "depth": "shallow"})
        data = response.get_json()
        assert "estimated_time" in data
        
        # Test medium
        response = client.post('/api/curious/trigger',
                              json={"topic": "test", "depth": "medium"})
        data = response.get_json()
        assert "estimated_time" in data
        
        # Test deep
        response = client.post('/api/curious/trigger',
                              json={"topic": "test", "depth": "deep"})
        data = response.get_json()
        assert "estimated_time" in data

    def test_trigger_accepts_all_valid_depths(self, client):
        """Test trigger accepts all valid depth values"""
        for depth in ["shallow", "medium", "deep"]:
            response = client.post('/api/curious/trigger',
                                  json={"topic": f"test {depth}", "depth": depth})
            assert response.status_code == 202, f"Failed for depth: {depth}"

    def test_trigger_handles_empty_topic(self, client):
        """Test trigger rejects empty topic"""
        response = client.post('/api/curious/trigger',
                              json={"topic": "", "depth": "shallow"})
        
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data

    def test_trigger_handles_whitespace_topic(self, client):
        """Test trigger rejects whitespace-only topic"""
        response = client.post('/api/curious/trigger',
                              json={"topic": "   ", "depth": "shallow"})
        
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data
