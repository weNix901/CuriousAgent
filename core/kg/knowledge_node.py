"""Pydantic models for Knowledge Node structure (v0.3.3)."""
from typing import List, Optional
from pydantic import BaseModel, Field


class KnowledgeContent(BaseModel):
    """Core content of a knowledge point."""
    definition: str  # Required: what is this concept
    formula: Optional[str] = None  # Key formula or code pattern
    fact: Optional[str] = None  # Key facts or properties
    examples: Optional[List[str]] = None  # Concrete examples
    completeness_score: int = Field(default=1, ge=1, le=6)


class KnowledgeSource(BaseModel):
    """Source metadata for traceability."""
    source_url: Optional[str] = None
    source_isbn: Optional[str] = None
    source_doi: Optional[str] = None
    source_internal_id: Optional[str] = None
    source_reference: Optional[str] = None
    source_type: str = "web"  # paper|book|manual|report|news|web|internal
    source_domain: Optional[str] = None
    source_publisher: Optional[str] = None
    source_trusted: bool = False
    local_file_path: Optional[str] = None
    local_file_type: Optional[str] = None  # pdf|html|epub|docx|markdown
    extracted_text_path: Optional[str] = None
    source_missing: bool = False


class KnowledgeRelations(BaseModel):
    """Relationships to other knowledge nodes."""
    parent: Optional[str] = None
    children: Optional[List[str]] = None
    depends_on: Optional[List[str]] = None
    related_to: Optional[List[str]] = None
    cites: Optional[List[str]] = None
    applied_in: Optional[List[str]] = None


class KnowledgeCitation(BaseModel):
    """Citation metadata."""
    citation_title: Optional[str] = None
    citation_authors: Optional[List[str]] = None
    citation_year: Optional[int] = None
    citation_venue: Optional[str] = None


class KnowledgeNode(BaseModel):
    """Complete knowledge node structure."""
    topic: str  # Primary key
    content: KnowledgeContent
    source: KnowledgeSource
    relations: KnowledgeRelations
    citation: KnowledgeCitation
    keywords: Optional[List[str]] = None
    heat: int = 0
    quality: float = 0.0
    status: str = "pending"  # pending|done|dormant
    deep_read_status: str = "pending"  # pending|processing|completed|failed