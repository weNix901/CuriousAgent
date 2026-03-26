from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Relation:
    from_topic: str
    to_topic: str
    relation_type: str
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class Topic:
    name: str
    known: bool = False
    depth: float = 0.0
    summary: str = ""
    sources: list = field(default_factory=list)
    status: str = "unexplored"
    explore_count: int = 0
    marginal_returns: list = field(default_factory=list)
    last_quality: float = 0.0
    parents: list = field(default_factory=list)
    children: list = field(default_factory=list)
    relations: list = field(default_factory=list)
    explored_by: list = field(default_factory=list)
    fully_explored: bool = False
    explored: bool = False
    created_at: datetime = field(default_factory=datetime.now)
    explored_at: datetime = None
    fully_explored_at: datetime = None
    schema_version: str = "2.0"
    
    def add_parent(self, parent: str) -> None:
        if parent not in self.parents:
            self.parents.append(parent)
    
    def add_child(self, child: str) -> None:
        if child not in self.children:
            self.children.append(child)
    
    def mark_explored(self, by: str = None) -> None:
        self.known = True
        self.explored = True
        self.status = "partial"
        self.explored_at = datetime.now()
        if by and by not in self.explored_by:
            self.explored_by.append(by)
    
    def mark_fully_explored(self) -> None:
        self.fully_explored = True
        self.status = "complete"
        self.fully_explored_at = datetime.now()
    
    @property
    def degree(self) -> int:
        return len(self.parents) + len(self.children)
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "known": self.known,
            "depth": self.depth,
            "summary": self.summary,
            "sources": self.sources,
            "status": self.status,
            "explore_count": self.explore_count,
            "marginal_returns": self.marginal_returns,
            "last_quality": self.last_quality,
            "parents": self.parents,
            "children": self.children,
            "relations": self.relations,
            "explored_by": self.explored_by,
            "fully_explored": self.fully_explored,
            "explored": self.explored,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "explored_at": self.explored_at.isoformat() if self.explored_at else None,
            "fully_explored_at": self.fully_explored_at.isoformat() if self.fully_explored_at else None,
            "schema_version": self.schema_version,
        }
    
    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            name=data["name"],
            known=data.get("known", False),
            depth=data.get("depth", 0.0),
            summary=data.get("summary", ""),
            sources=data.get("sources", []),
            status=data.get("status", "unexplored"),
            explore_count=data.get("explore_count", 0),
            marginal_returns=data.get("marginal_returns", []),
            last_quality=data.get("last_quality", 0.0),
            parents=data.get("parents", []),
            children=data.get("children", []),
            relations=data.get("relations", []),
            explored_by=data.get("explored_by", []),
            fully_explored=data.get("fully_explored", False),
            explored=data.get("explored", False),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(),
            explored_at=datetime.fromisoformat(data["explored_at"]) if data.get("explored_at") else None,
            fully_explored_at=datetime.fromisoformat(data["fully_explored_at"]) if data.get("fully_explored_at") else None,
            schema_version=data.get("schema_version", "2.0"),
        )
