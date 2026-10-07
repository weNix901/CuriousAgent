"""Tests for agent configurations."""
import pytest


class TestExploreAgentConfig:
    """Tests for ExploreAgentConfig."""

    def test_import_explore_config(self):
        from core.configs.agent_explore import ExploreAgentConfig
        assert ExploreAgentConfig is not None

    def test_explore_config_has_name(self):
        from core.configs.agent_explore import ExploreAgentConfig
        config = ExploreAgentConfig()
        assert config.name == "ExploreAgent"

    def test_explore_config_has_system_prompt(self):
        from core.configs.agent_explore import ExploreAgentConfig
        config = ExploreAgentConfig()
        assert config.system_prompt is not None
        assert len(config.system_prompt) > 0

    def test_explore_config_has_tools(self):
        from core.configs.agent_explore import ExploreAgentConfig
        config = ExploreAgentConfig()
        assert len(config.tools) == 14

    def test_explore_config_max_iterations(self):
        from core.configs.agent_explore import ExploreAgentConfig
        config = ExploreAgentConfig()
        assert config.max_iterations == 10


class TestDreamAgentConfig:
    """Tests for DreamAgentConfig."""

    def test_import_dream_config(self):
        from core.configs.agent_dream import DreamAgentConfig
        assert DreamAgentConfig is not None

    def test_dream_config_has_name(self):
        from core.configs.agent_dream import DreamAgentConfig
        config = DreamAgentConfig()
        assert config.name == "DreamAgent"

    def test_dream_config_has_scoring_weights(self):
        from core.configs.agent_dream import DreamAgentConfig
        config = DreamAgentConfig()
        assert config.scoring_weights is not None
        assert len(config.scoring_weights) == 6

    def test_dream_config_has_threshold(self):
        from core.configs.agent_dream import DreamAgentConfig
        config = DreamAgentConfig()
        assert config.min_score_threshold == 0.8

    def test_dream_config_tools_count(self):
        from core.configs.agent_dream import DreamAgentConfig
        config = DreamAgentConfig()
        assert len(config.tools) >= 13