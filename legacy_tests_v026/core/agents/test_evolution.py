"""Tests for SelfEvolution class."""
import pytest
import os
import json
from pathlib import Path


class TestSelfEvolutionImport:
    """Test SelfEvolution class can be imported."""

    def test_import_self_evolution(self):
        """SelfEvolution should be importable from core.agents.evolution."""
        from core.agents.evolution import SelfEvolution
        assert SelfEvolution is not None


class TestSelfEvolutionInit:
    """Test SelfEvolution initialization."""

    def test_init_creates_instance(self):
        """SelfEvolution should initialize with default state path."""
        from core.agents.evolution import SelfEvolution
        
        evolution = SelfEvolution()
        
        assert evolution is not None

    def test_init_has_strategy_weights(self):
        """SelfEvolution should have strategy_weights attribute."""
        from core.agents.evolution import SelfEvolution
        
        evolution = SelfEvolution()
        
        assert hasattr(evolution, 'strategy_weights')
        assert isinstance(evolution.strategy_weights, dict)

    def test_init_has_default_strategies(self):
        """SelfEvolution should have default strategies: exploration_depth, provider_selection, quality_threshold."""
        from core.agents.evolution import SelfEvolution
        
        evolution = SelfEvolution()
        
        expected_strategies = ['exploration_depth', 'provider_selection', 'quality_threshold']
        for strategy in expected_strategies:
            assert strategy in evolution.strategy_weights

    def test_init_has_success_history(self):
        """SelfEvolution should have success_history attribute."""
        from core.agents.evolution import SelfEvolution
        
        evolution = SelfEvolution()
        
        assert hasattr(evolution, 'success_history')
        assert isinstance(evolution.success_history, dict)


class TestRecordStrategyResult:
    """Test record_strategy_result method."""

    def test_record_strategy_result_method_exists(self):
        """SelfEvolution should have record_strategy_result method."""
        from core.agents.evolution import SelfEvolution
        
        evolution = SelfEvolution()
        
        assert hasattr(evolution, 'record_strategy_result')

    def test_record_strategy_result_records_success(self):
        """record_strategy_result should record success rate for a strategy."""
        from core.agents.evolution import SelfEvolution
        
        evolution = SelfEvolution()
        evolution.record_strategy_result('exploration_depth', 0.85, {'context': 'test'})
        
        assert 'exploration_depth' in evolution.success_history
        assert len(evolution.success_history['exploration_depth']) > 0

    def test_record_strategy_result_stores_context(self):
        """record_strategy_result should store context with the result."""
        from core.agents.evolution import SelfEvolution
        
        evolution = SelfEvolution()
        context = {'topic': 'agent_memory', 'depth': 5}
        evolution.record_strategy_result('provider_selection', 0.75, context)
        
        last_result = evolution.success_history['provider_selection'][-1]
        assert last_result['context'] == context

    def test_record_strategy_result_appends_multiple_records(self):
        """record_strategy_result should append multiple records for same strategy."""
        from core.agents.evolution import SelfEvolution
        
        evolution = SelfEvolution()
        evolution.record_strategy_result('quality_threshold', 0.6, {})
        evolution.record_strategy_result('quality_threshold', 0.8, {})
        
        assert len(evolution.success_history['quality_threshold']) == 2


class TestUpdateStrategyWeights:
    """Test update_strategy_weights method."""

    def test_update_strategy_weights_method_exists(self):
        """SelfEvolution should have update_strategy_weights method."""
        from core.agents.evolution import SelfEvolution
        
        evolution = SelfEvolution()
        
        assert hasattr(evolution, 'update_strategy_weights')

    def test_update_strategy_weights_updates_weights(self):
        """update_strategy_weights should adjust weights based on success rates."""
        from core.agents.evolution import SelfEvolution
        
        evolution = SelfEvolution()
        evolution.record_strategy_result('exploration_depth', 0.9, {})
        evolution.update_strategy_weights()
        
        assert 'exploration_depth' in evolution.strategy_weights

    def test_update_strategy_weights_uses_ema(self):
        """update_strategy_weights should use EMA (Exponential Moving Average) for smooth updates."""
        from core.agents.evolution import SelfEvolution
        
        evolution = SelfEvolution()
        initial_weight = evolution.strategy_weights.get('exploration_depth', 0.5)
        
        # Record high success rate
        evolution.record_strategy_result('exploration_depth', 0.95, {})
        evolution.update_strategy_weights()
        
        new_weight = evolution.strategy_weights['exploration_depth']
        
        # Weight should move towards success rate but not jump completely (EMA property)
        assert new_weight > initial_weight  # Should increase
        assert new_weight < 0.95  # Should not reach full success rate (EMA smoothing)

    def test_update_strategy_weights_handles_multiple_strategies(self):
        """update_strategy_weights should handle multiple strategies independently."""
        from core.agents.evolution import SelfEvolution
        
        evolution = SelfEvolution()
        evolution.record_strategy_result('exploration_depth', 0.9, {})
        evolution.record_strategy_result('provider_selection', 0.3, {})
        evolution.update_strategy_weights()
        
        # High success should increase weight
        assert evolution.strategy_weights['exploration_depth'] > 0.5
        # Low success should decrease or keep low weight
        assert evolution.strategy_weights['provider_selection'] < 0.5


class TestGetBestStrategy:
    """Test get_best_strategy method."""

    def test_get_best_strategy_method_exists(self):
        """SelfEvolution should have get_best_strategy method."""
        from core.agents.evolution import SelfEvolution
        
        evolution = SelfEvolution()
        
        assert hasattr(evolution, 'get_best_strategy')

    def test_get_best_strategy_returns_strategy_name(self):
        """get_best_strategy should return the name of the best strategy."""
        from core.agents.evolution import SelfEvolution
        
        evolution = SelfEvolution()
        
        strategy = evolution.get_best_strategy({})
        
        assert isinstance(strategy, str)
        assert strategy in ['exploration_depth', 'provider_selection', 'quality_threshold']

    def test_get_best_strategy_returns_highest_weight(self):
        """get_best_strategy should return strategy with highest weight."""
        from core.agents.evolution import SelfEvolution
        
        evolution = SelfEvolution()
        # Manually set weights to test selection
        evolution.strategy_weights = {
            'exploration_depth': 0.3,
            'provider_selection': 0.9,
            'quality_threshold': 0.5
        }
        
        best = evolution.get_best_strategy({})
        
        assert best == 'provider_selection'


class TestStatePersistence:
    """Test state persistence to knowledge/evolution_state.json."""

    def test_state_file_path_attribute(self):
        """SelfEvolution should have state_file_path attribute."""
        from core.agents.evolution import SelfEvolution
        
        evolution = SelfEvolution()
        
        assert hasattr(evolution, 'state_file_path')
        assert 'evolution_state.json' in str(evolution.state_file_path)

    def test_save_state_method_exists(self):
        """SelfEvolution should have save_state method."""
        from core.agents.evolution import SelfEvolution
        
        evolution = SelfEvolution()
        
        assert hasattr(evolution, 'save_state')

    def test_load_state_method_exists(self):
        """SelfEvolution should have load_state method."""
        from core.agents.evolution import SelfEvolution
        
        evolution = SelfEvolution()
        
        assert hasattr(evolution, 'load_state')

    def test_save_and_load_state_persists_weights(self):
        """save_state and load_state should persist strategy weights."""
        from core.agents.evolution import SelfEvolution
        import tempfile
        
        # Use temp directory for test
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / 'test_evolution_state.json'
            evolution = SelfEvolution(state_file_path=state_path)
            
            # Modify weights
            evolution.strategy_weights['exploration_depth'] = 0.85
            evolution.save_state()
            
            # Load in new instance
            evolution2 = SelfEvolution(state_file_path=state_path)
            evolution2.load_state()
            
            assert evolution2.strategy_weights['exploration_depth'] == 0.85

    def test_save_and_load_state_persists_history(self):
        """save_state and load_state should persist success history."""
        from core.agents.evolution import SelfEvolution
        import tempfile
        
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / 'test_evolution_state.json'
            evolution = SelfEvolution(state_file_path=state_path)
            
            # Record some history
            evolution.record_strategy_result('quality_threshold', 0.75, {'test': True})
            evolution.save_state()
            
            # Load in new instance
            evolution2 = SelfEvolution(state_file_path=state_path)
            evolution2.load_state()
            
            assert len(evolution2.success_history['quality_threshold']) == 1
