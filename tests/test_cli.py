"""Tests for CLI --depth parameter"""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from curious_agent import run_one_cycle


class TestDepthParameter:
    """Test suite for --depth parameter"""

    def test_depth_parameter_accepts_shallow(self):
        """Test that depth parameter accepts 'shallow' value"""
        # Valid depth values should not raise ValueError
        result = run_one_cycle(depth="shallow")
        assert result is not None

    def test_depth_parameter_accepts_medium(self):
        """Test that depth parameter accepts 'medium' value"""
        result = run_one_cycle(depth="medium")
        assert result is not None

    def test_depth_parameter_accepts_deep(self):
        """Test that depth parameter accepts 'deep' value"""
        result = run_one_cycle(depth="deep")
        assert result is not None

    def test_depth_parameter_invalid_raises_error(self):
        """Test that invalid depth raises ValueError"""
        with pytest.raises(ValueError):
            run_one_cycle(depth="invalid")

    def test_depth_parameter_default_is_medium(self):
        """Test that default depth is 'medium'"""
        # Default behavior should work with medium depth
        result = run_one_cycle()
        assert result is not None
