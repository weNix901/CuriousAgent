import pytest
from abc import ABC
from core.repository.base import KnowledgeRepository


class TestRepositoryInterface:
    def test_is_abstract_class(self):
        assert issubclass(KnowledgeRepository, ABC)
    
    def test_cannot_instantiate_directly(self):
        with pytest.raises(TypeError):
            KnowledgeRepository()
