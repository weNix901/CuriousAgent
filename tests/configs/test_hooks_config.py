"""Test hooks configuration."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest
from core.config import get_config, CognitiveHookConfig


class TestHooksConfig:
    """Test hooks configuration loading."""

    def test_hooks_config_exists(self):
        """Config should have hooks field."""
        cfg = get_config()
        assert hasattr(cfg, 'hooks'), "Config should have hooks field"

    def test_cognitive_hook_config_defaults(self):
        """CognitiveHookConfig should have correct defaults."""
        cfg = get_config()
        assert cfg.hooks.confidence_threshold == 0.6
        assert cfg.hooks.auto_inject_unknowns == True
        assert cfg.hooks.search_before_llm == True
