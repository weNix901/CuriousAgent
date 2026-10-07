import pytest
import tempfile
import os
import json
from core.r1d3_watcher import R1D3Watcher


class TestR1D3Watcher:
    @pytest.fixture
    def watcher(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            watcher = R1D3Watcher(tmpdir)
            yield watcher
    
    def test_scan_new_propositions_empty(self, watcher):
        props = watcher.scan_new_propositions()
        assert props == []
    
    def test_scan_new_proposition(self, watcher):
        prop = {"proposition": "Test topic", "seed_topics": ["test"]}
        with open(os.path.join(watcher.propositions_dir, "001_test.json"), "w") as f:
            json.dump(prop, f)
        
        props = watcher.scan_new_propositions()
        
        assert len(props) == 1
        assert props[0]["proposition"] == "Test topic"
        assert props[0]["seed_topics"] == ["test"]
    
    def test_no_duplicate_scan(self, watcher):
        prop = {"proposition": "Test", "seed_topics": ["test"]}
        with open(os.path.join(watcher.propositions_dir, "001.json"), "w") as f:
            json.dump(prop, f)
        
        first = watcher.scan_new_propositions()
        second = watcher.scan_new_propositions()
        
        assert len(first) == 1
        assert len(second) == 0
    
    def test_ignore_non_json(self, watcher):
        with open(os.path.join(watcher.propositions_dir, "readme.txt"), "w") as f:
            f.write("not json")
        
        props = watcher.scan_new_propositions()
        assert props == []
    
    def test_get_seed_topics(self, watcher):
        prop = {"proposition": "Test", "seed_topics": ["a", "b"]}
        topics = watcher.get_seed_topics(prop)
        assert topics == ["a", "b"]
    
    def test_get_seed_topics_empty(self, watcher):
        prop = {"proposition": "Test"}
        topics = watcher.get_seed_topics(prop)
        assert topics == []
