"""Tests for CLI agent flags (--explore, --dream, --daemon-explore, --daemon-dream)."""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from curious_agent import run_explore_agent, run_dream_agent


class TestExploreAgentCLI:
    """Test suite for --explore CLI flag."""

    def test_run_explore_agent_returns_dict(self):
        """Test that run_explore_agent returns a dict with expected keys."""
        result = run_explore_agent("test_topic")
        assert isinstance(result, dict)
        assert "status" in result
        assert "topic" in result
        assert "iterations" in result
        assert "content" in result

    def test_run_explore_agent_status_is_success_or_failed(self):
        """Test that status is either 'success' or 'failed'."""
        result = run_explore_agent("test_topic")
        assert result["status"] in ("success", "failed")

    def test_run_explore_agent_topic_matches_input(self):
        """Test that returned topic matches input."""
        result = run_explore_agent("agent memory")
        assert result["topic"] == "agent memory"


class TestDreamAgentCLI:
    """Test suite for --dream CLI flag."""

    def test_run_dream_agent_returns_dict(self):
        """Test that run_dream_agent returns a dict with expected keys."""
        result = run_dream_agent()
        assert isinstance(result, dict)
        assert "status" in result
        assert "topics_generated" in result
        assert "candidates_selected" in result
        assert "content" in result

    def test_run_dream_agent_status_is_success_or_failed(self):
        """Test that status is either 'success' or 'failed'."""
        result = run_dream_agent()
        assert result["status"] in ("success", "failed")

    def test_run_dream_agent_topics_generated_is_list(self):
        """Test that topics_generated is a list."""
        result = run_dream_agent()
        assert isinstance(result["topics_generated"], list)