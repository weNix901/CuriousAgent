from abc import ABC, abstractmethod
from core.models.topic import Topic


class KnowledgeRepository(ABC):
    @abstractmethod
    def get_topic(self, name: str):
        pass
    
    @abstractmethod
    def save_topic(self, topic: Topic):
        pass
    
    @abstractmethod
    def get_all_topics(self):
        pass
    
    @abstractmethod
    def add_relation(self, from_topic: str, to_topic: str, relation_type: str = "associated"):
        pass
    
    @abstractmethod
    def get_neighbors(self, topic: str, relation_type: str = None):
        pass
    
    @abstractmethod
    def get_high_degree_unexplored(self):
        pass
    
    @abstractmethod
    def get_storage_path(self):
        pass
