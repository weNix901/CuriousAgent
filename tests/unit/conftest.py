"""Unit test isolation (v0.3.7 B-2).

Unit tests must be fully offline: no real Neo4j, no production ops.db / queue.db.
Any test needing external services belongs in tests/integration/.
"""
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


@pytest.fixture
def tmp_db(tmp_path):
    """An isolated sqlite path that never touches production knowledge/*.db."""
    return str(tmp_path / "test.db")


@pytest.fixture(autouse=True)
def _no_prod_db_env(monkeypatch):
    """Point any DB env var at a temp dir so unit tests can't write production."""
    d = tempfile.mkdtemp(prefix="ca_unit_")
    for var in ("CA_QUEUE_DB", "CA_OPS_DB", "QUEUE_DB", "OPS_DB"):
        monkeypatch.setenv(var, os.path.join(d, "isolated.db"))
    yield
