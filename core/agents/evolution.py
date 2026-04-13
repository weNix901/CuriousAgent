"""Self-evolution engine for Curious Agent."""
import json
from pathlib import Path
from typing import Any, Optional


# Module-level constant for EMA smoothing factor
EMA_ALPHA = 0.3  # Smoothing factor for EMA (0.3 = 30% new, 70% old)

__all__ = ['SelfEvolution', 'EMA_ALPHA']


class SelfEvolution:
    """Self-evolution engine that tracks and optimizes strategy performance.
    
    Uses Exponential Moving Average (EMA) to smoothly adjust strategy weights
    based on observed success rates.
    """
    
    DEFAULT_STRATEGIES = ['exploration_depth', 'provider_selection', 'quality_threshold']
    DEFAULT_WEIGHT = 0.5
    EMA_ALPHA = 0.3  # Smoothing factor for EMA (0.3 = 30% new, 70% old)
    
    def __init__(self, state_file_path: Optional[Path] = None):
        """Initialize SelfEvolution with optional custom state file path.
        
        Args:
            state_file_path: Path to evolution state JSON file.
                            Defaults to knowledge/evolution_state.json
        """
        self.state_file_path = state_file_path or Path('knowledge/evolution_state.json')
        self.strategy_weights: dict[str, float] = {}
        self.success_history: dict[str, list[dict[str, Any]]] = {}
        
        # Initialize default strategies
        for strategy in self.DEFAULT_STRATEGIES:
            if strategy not in self.strategy_weights:
                self.strategy_weights[strategy] = self.DEFAULT_WEIGHT
            if strategy not in self.success_history:
                self.success_history[strategy] = []
        
        # Load existing state if available
        self.load_state()
    
    def record_strategy_result(self, strategy_name: str, success_rate: float, context: dict[str, Any]) -> None:
        """Record the result of a strategy execution.
        
        Args:
            strategy_name: Name of the strategy (e.g., 'exploration_depth')
            success_rate: Success rate value (0.0 to 1.0)
            context: Contextual information about the strategy execution
        """
        if strategy_name not in self.success_history:
            self.success_history[strategy_name] = []
            if strategy_name not in self.strategy_weights:
                self.strategy_weights[strategy_name] = self.DEFAULT_WEIGHT
        
        self.success_history[strategy_name].append({
            'success_rate': success_rate,
            'context': context
        })
    
    def update_strategy_weights(self) -> None:
        """Update strategy weights using Exponential Moving Average (EMA).
        
        EMA formula: new_weight = alpha * success_rate + (1 - alpha) * old_weight
        This provides smooth weight adjustments without sudden jumps.
        """
        for strategy_name, history in self.success_history.items():
            if not history:
                continue
            
            # Calculate average success rate from history
            avg_success_rate = sum(record['success_rate'] for record in history) / len(history)
            
            # Apply EMA update
            old_weight = self.strategy_weights.get(strategy_name, self.DEFAULT_WEIGHT)
            new_weight = self.EMA_ALPHA * avg_success_rate + (1 - self.EMA_ALPHA) * old_weight
            
            self.strategy_weights[strategy_name] = new_weight
    
    def get_best_strategy(self, context: dict[str, Any]) -> str:
        """Get the best strategy for the given context.
        
        Args:
            context: Contextual information for strategy selection
            
        Returns:
            Name of the strategy with highest weight
        """
        if not self.strategy_weights:
            return self.DEFAULT_STRATEGIES[0]
        
        return max(self.strategy_weights.keys(), key=lambda k: self.strategy_weights[k])
    
    def save_state(self) -> None:
        """Save current state to JSON file."""
        # Ensure directory exists
        self.state_file_path.parent.mkdir(parents=True, exist_ok=True)
        
        state = {
            'strategy_weights': self.strategy_weights,
            'success_history': self.success_history
        }
        
        with open(self.state_file_path, 'w') as f:
            json.dump(state, f, indent=2)
    
    def load_state(self) -> None:
        """Load state from JSON file if it exists."""
        if not self.state_file_path.exists():
            return
        
        try:
            with open(self.state_file_path, 'r') as f:
                state = json.load(f)
            
            self.strategy_weights = state.get('strategy_weights', self.strategy_weights)
            self.success_history = state.get('success_history', self.success_history)
        except (json.JSONDecodeError, IOError):
            # If file is corrupted, start fresh
            pass
