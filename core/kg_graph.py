from typing import Optional
from core.repository.base import KnowledgeRepository


class KGGraph:
    """Knowledge Graph structure manager with multi-parent support"""
    
    def __init__(self, repo: KnowledgeRepository):
        self.repo = repo
    
    def should_explore(self, node: str, from_parent: Optional[str] = None) -> tuple[bool, str]:
        """
        Determine if a node should be explored
        
        Returns:
            (True, "first_visit") - New node, needs exploration
            (True, "not_yet_explored") - Exists but not explored
            (False, "linked_only") - Already explored, only update relation
            (False, "already_explored") - Already explored and known parent
        """
        topic = self.repo.get_topic(node)
        
        if not topic:
            return True, "first_visit"
        
        if not topic.explored:
            return True, "not_yet_explored"
        
        if from_parent and from_parent in topic.parents:
            return False, "already_explored"
        
        return False, "linked_only"
    
    def add_relation(self, from_topic: str, to_topic: str, relation_type: str = "associated"):
        """Add bidirectional relation"""
        self.repo.add_relation(from_topic, to_topic, relation_type)
    
    def get_high_degree_unexplored(self) -> Optional[str]:
        """Return highest degree unexplored node"""
        return self.repo.get_high_degree_unexplored()
    
    def get_topic(self, name: str):
        """Get topic by name"""
        return self.repo.get_topic(name)
