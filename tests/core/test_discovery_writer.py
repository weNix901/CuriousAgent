import pytest
import tempfile
import os
import json
from core.discovery_writer import DiscoveryWriter


class TestDiscoveryWriter:
    @pytest.fixture
    def writer(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            writer = DiscoveryWriter(tmpdir)
            yield writer
    
    def test_write_discovery(self, writer):
        filepath = writer.write_discovery(
            topic="attention mechanism",
            findings="发现新的线性注意力",
            quality=8.5,
            surprise={"is_surprise": True, "surprise_level": 0.8}
        )
        
        assert os.path.exists(filepath)
        
        with open(filepath) as f:
            data = json.load(f)
        
        assert data["topic"] == "attention mechanism"
        assert data["findings_summary"] == "发现新的线性注意力"
        assert data["quality_score"] == 8.5
        assert data["is_surprise"] is True
        assert data["surprise_level"] == 0.8
        assert "timestamp" in data
    
    def test_write_discovery_no_surprise(self, writer):
        filepath = writer.write_discovery(
            topic="test",
            findings="普通发现",
            quality=6.0,
        )
        
        with open(filepath) as f:
            data = json.load(f)
        
        assert data["is_surprise"] is False
        assert data["surprise_level"] == 0.0
    
    def test_write_creates_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            disc_dir = os.path.join(tmpdir, "subdir", "discoveries")
            writer = DiscoveryWriter(disc_dir)
            
            writer.write_discovery("test", "findings", 5.0)
            
            assert os.path.exists(disc_dir)
    
    def test_filename_contains_topic_slug(self, writer):
        filepath = writer.write_discovery("Attention Mechanism", "findings", 5.0)
        
        filename = os.path.basename(filepath)
        assert "attention-mechanism" in filename
        assert filename.endswith(".json")
