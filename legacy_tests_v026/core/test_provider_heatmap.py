import pytest
from core.provider_heatmap import ProviderHeatmap, get_heatmap


def test_record_and_get_coverage():
    heatmap = ProviderHeatmap()
    heatmap.record_verification("en", "AI/agent", {"bocha": 100, "serper": 50})
    
    coverage = heatmap.get_coverage("en", "AI/agent")
    assert coverage["bocha"] == 100
    assert coverage["serper"] == 50


def test_get_best_providers():
    heatmap = ProviderHeatmap()
    heatmap.record_verification("en", "AI", {"serper": 200, "bocha": 100})
    
    best = heatmap.get_best_providers("en", "AI")
    assert best[0] == "serper"


def test_singleton():
    h1 = get_heatmap()
    h2 = get_heatmap()
    assert h1 is h2
