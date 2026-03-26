from dataclasses import dataclass, field


@dataclass
class SpiderRuntimeState:
    current_node: str = None
    frontier: list = field(default_factory=list)
    visited: set = field(default_factory=set)
    consecutive_low_gain: int = 0
    step_count: int = 0
    
    def to_dict(self):
        return {
            "current_node": self.current_node,
            "frontier": self.frontier,
            "visited": list(self.visited),
            "consecutive_low_gain": self.consecutive_low_gain,
            "step_count": self.step_count,
        }
    
    @classmethod
    def from_dict(cls, data):
        return cls(
            current_node=data.get("current_node"),
            frontier=data.get("frontier", []),
            visited=set(data.get("visited", [])),
            consecutive_low_gain=data.get("consecutive_low_gain", 0),
            step_count=data.get("step_count", 0),
        )
