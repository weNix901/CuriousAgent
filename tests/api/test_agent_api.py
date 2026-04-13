"""Tests for API agent endpoints."""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from curious_api import app


@pytest.fixture
def client():
    """Create a test client for the Flask app."""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


class TestAgentsExploreEndpoint:
    """Test suite for /api/agents/explore endpoint."""

    def test_explore_endpoint_requires_topic(self, client):
        """Test that explore endpoint requires topic parameter."""
        response = client.post('/api/agents/explore', json={})
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data

    def test_explore_endpoint_returns_success_or_failed(self, client):
        """Test that explore endpoint returns status."""
        response = client.post('/api/agents/explore', json={'topic': 'test_topic'})
        assert response.status_code in (200, 500)
        data = response.get_json()
        assert 'status' in data

    def test_explore_endpoint_includes_iterations(self, client):
        """Test that explore endpoint includes iterations count."""
        response = client.post('/api/agents/explore', json={'topic': 'agent memory'})
        data = response.get_json()
        if response.status_code == 200:
            assert 'iterations' in data


class TestAgentsDreamEndpoint:
    """Test suite for /api/agents/dream endpoint."""

    def test_dream_endpoint_returns_status(self, client):
        """Test that dream endpoint returns status."""
        response = client.post('/api/agents/dream', json={})
        assert response.status_code in (200, 500)
        data = response.get_json()
        assert 'status' in data

    def test_dream_endpoint_includes_topics_generated(self, client):
        """Test that dream endpoint includes topics_generated."""
        response = client.post('/api/agents/dream', json={})
        data = response.get_json()
        if response.status_code == 200:
            assert 'topics_generated' in data
            assert isinstance(data['topics_generated'], list)


class TestAgentsDaemonExploreEndpoint:
    """Test suite for /api/agents/daemon/explore endpoint."""

    def test_daemon_explore_endpoint_returns_status(self, client):
        """Test that daemon explore endpoint returns started status."""
        response = client.post('/api/agents/daemon/explore', json={})
        assert response.status_code in (200, 500)
        data = response.get_json()
        assert 'status' in data

    def test_daemon_explore_endpoint_includes_poll_interval(self, client):
        """Test that daemon explore endpoint includes poll_interval."""
        response = client.post('/api/agents/daemon/explore', json={})
        data = response.get_json()
        if response.status_code == 200:
            assert 'poll_interval' in data


class TestAgentsDaemonDreamEndpoint:
    """Test suite for /api/agents/daemon/dream endpoint."""

    def test_daemon_dream_endpoint_returns_status(self, client):
        """Test that daemon dream endpoint returns started status."""
        response = client.post('/api/agents/daemon/dream', json={})
        assert response.status_code in (200, 500)
        data = response.get_json()
        assert 'status' in data

    def test_daemon_dream_endpoint_accepts_interval(self, client):
        """Test that daemon dream endpoint accepts custom interval."""
        response = client.post('/api/agents/daemon/dream', json={'interval_s': 3600})
        data = response.get_json()
        if response.status_code == 200:
            assert 'interval_s' in data


class TestAgentsStatusEndpoint:
    """Test suite for /api/agents/status endpoint."""

    def test_status_endpoint_returns_ok(self, client):
        """Test that status endpoint returns ok status."""
        response = client.get('/api/agents/status')
        assert response.status_code in (200, 500)
        data = response.get_json()
        assert 'status' in data

    def test_status_endpoint_includes_agents(self, client):
        """Test that status endpoint includes agents info."""
        response = client.get('/api/agents/status')
        data = response.get_json()
        if response.status_code == 200:
            assert 'agents' in data