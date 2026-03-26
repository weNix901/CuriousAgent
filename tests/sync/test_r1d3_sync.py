import pytest
import json
import tempfile
from pathlib import Path
from core.sync.r1d3_sync import R1D3Sync


def test_mark_discovery_shared():
    with tempfile.TemporaryDirectory() as tmpdir:
        sync = R1D3Sync(discoveries_dir=tmpdir)
        
        discovery_file = Path(tmpdir) / "test_discovery.json"
        with open(discovery_file, 'w') as f:
            json.dump({"topic": "test", "shared": False}, f)
        
        result = sync.mark_discovery_shared("test_discovery.json")
        
        assert result is True
        
        with open(discovery_file, 'r') as f:
            data = json.load(f)
        
        assert data['shared'] is True
        assert 'shared_at' in data


def test_get_unshared_discoveries():
    with tempfile.TemporaryDirectory() as tmpdir:
        sync = R1D3Sync(discoveries_dir=tmpdir)
        
        # Create unshared discovery
        with open(Path(tmpdir) / "unshared.json", 'w') as f:
            json.dump({"topic": "unshared", "shared": False}, f)
        
        # Create shared discovery
        with open(Path(tmpdir) / "shared.json", 'w') as f:
            json.dump({"topic": "shared", "shared": True}, f)
        
        result = sync.get_unshared_discoveries()
        
        assert len(result) == 1
        assert result[0]["topic"] == "unshared"
