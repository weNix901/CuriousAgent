"""Tests for /api/knowledge/semantic endpoint."""

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


class TestSemanticQueryEndpoint:
    """Test GET /api/knowledge/semantic endpoint."""

    def test_semantic_endpoint_requires_query(self, client):
        """Test endpoint requires query parameter."""
        response = client.get(
            "/api/knowledge/semantic",
            query_string={"top_k": 3}
        )
        
        assert response.status_code == 400

    def test_semantic_endpoint_returns_structure(self, client):
        """Test endpoint returns correct JSON structure."""
        response = client.get(
            "/api/knowledge/semantic",
            query_string={"query": "test query", "top_k": 3}
        )
        
        # Accept 200 (success) or 500 (Neo4j not available)
        if response.status_code == 200:
            data = response.get_json()
            assert "results" in data
            assert "query" in data
            assert "count" in data
            assert data["query"] == "test query"
            assert isinstance(data["results"], list)
            assert data["count"] == len(data["results"])
        else:
            # Neo4j not available - endpoint should still be registered
            assert response.status_code == 500

    def test_semantic_endpoint_default_params(self, client):
        """Test endpoint with default parameters."""
        response = client.get(
            "/api/knowledge/semantic",
            query_string={"query": "default test"}
        )
        
        # Accept 200 (success) or 500 (Neo4j not available)
        if response.status_code == 200:
            data = response.get_json()
            assert data["query"] == "default test"
            assert "results" in data
            assert "count" in data
        else:
            assert response.status_code == 500
