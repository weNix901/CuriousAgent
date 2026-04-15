"""E2E test for full cognitive answer loop."""

import pytest
import requests

BASE_URL = "http://localhost:4848"


@pytest.fixture(scope="module")
def api_available():
    """Check if API is running."""
    try:
        resp = requests.get(f"{BASE_URL}/api/curious/state", timeout=2)
        return resp.status_code == 200
    except:
        pytest.skip("API not running")


class TestCognitiveLoopE2E:
    """Test full cognitive answer loop."""

    def test_check_confidence_for_known_topic(self, api_available):
        """Known topic should return confidence."""
        resp = requests.post(
            f"{BASE_URL}/api/knowledge/check",
            json={"topic": "transformer attention"},
            timeout=10,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"]

    def test_check_confidence_for_unknown_topic(self, api_available):
        """Unknown topic should return novice level."""
        resp = requests.post(
            f"{BASE_URL}/api/knowledge/check",
            json={"topic": "BrandNewTopicXYZ123"},
            timeout=10,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"]
        assert data["result"]["level"] == "novice"

    def test_inject_and_analytics_cycle(self, api_available):
        """Full cycle: inject → analytics shows injection."""
        topic = "TestTopicE2E"
        
        # Inject
        resp = requests.post(
            f"{BASE_URL}/api/knowledge/learn",
            json={"topic": topic, "strategy": "llm_answer"},
            timeout=10,
        )
        assert resp.json()["success"]
        
        # Analytics
        resp = requests.get(f"{BASE_URL}/api/knowledge/analytics", timeout=10)
        assert resp.json()["topics_learned"] > 0
