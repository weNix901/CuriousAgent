"""Integration test config (v0.3.7 B-2/B-3).

Tests here may talk to a real (local) Neo4j. They are opt-in.
Run: pytest tests/integration -m integration
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def pytest_collection_modifyitems(config, items):
    """Auto-mark everything in tests/integration with @pytest.mark.integration."""
    for item in items:
        if "/integration/" in str(item.fspath).replace("\\", "/"):
            item.add_marker(pytest.mark.integration)
