"""Tests for TemperatureSystem (v0.3.3)."""
import pytest
from core.temperature_system import TemperatureSystem


class TestTemperatureSystem:
    def test_decay_reduces_heat(self):
        """Test exponential decay of heat."""
        system = TemperatureSystem()
        heat = 100
        for _ in range(10):
            heat = system.apply_decay(heat)
        # After 10 cycles with 0.95 decay, should be ~60
        assert 50 < heat < 70
    
    def test_hit_boost_increases_heat(self):
        """Test heat boost on retrieval."""
        system = TemperatureSystem()
        heat = 50
        heat = system.apply_hit(heat)
        assert heat == 70  # 50 + 20
    
    def test_classification_hot(self):
        """Test hot classification."""
        system = TemperatureSystem()
        assert system.classify(90) == "hot"
        assert system.classify(80) == "hot"
    
    def test_classification_warm(self):
        """Test warm classification."""
        system = TemperatureSystem()
        assert system.classify(50) == "warm"
        assert system.classify(30) == "warm"
    
    def test_classification_cold(self):
        """Test cold classification."""
        system = TemperatureSystem()
        assert system.classify(10) == "cold"
        assert system.classify(29) == "cold"
    
    def test_update_heat_full_cycle_with_hit(self):
        """Test full update cycle with retrieval hit."""
        system = TemperatureSystem()
        heat = 100
        for _ in range(5):
            heat = system.update_heat(heat, retrieved=True, child_count=3)
        assert heat >= 80  # Should stay hot with hits
    
    def test_update_heat_decay_without_hits(self):
        """Test heat decays without hits."""
        system = TemperatureSystem()
        heat = 50
        for _ in range(20):
            heat = system.update_heat(heat, retrieved=False, age_days=3)
        assert heat < 30  # Should become cold
    
    def test_trusted_multiplier(self):
        """Test trusted source multiplier."""
        system = TemperatureSystem()
        heat = system.apply_trusted(50, is_trusted=True)
        assert heat == pytest.approx(55.0)  # 50 * 1.1
    
    def test_heat_clamped_to_range(self):
        """Test heat is clamped to [0, 100]."""
        system = TemperatureSystem()
        # Can't exceed 100
        heat = system.update_heat(95, retrieved=True, child_count=10)
        assert heat <= 100
        # Can't go below 0
        heat = system.update_heat(0, retrieved=False)
        assert heat >= 0