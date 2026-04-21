# core/tools/paper_tools.py
"""Paper processing tools for Curious Agent v0.3.3."""
import hashlib
import os
import json
import logging
from typing import Any

from core.tools.base import Tool

logger = logging.getLogger(__name__)

PAPERS_DIR = "papers"


def paper_storage_paths(topic: str) -> tuple[str, str]:
    """Generate stable file paths for a paper topic.
    
    Args:
        topic: Paper topic string
        
    Returns:
        Tuple of (pdf_path, txt_path)
    """
    topic_hash = hashlib.md5(topic.encode()).hexdigest()[:12]
    pdf_path = f"{PAPERS_DIR}/{topic_hash}.pdf"
    txt_path = f"{PAPERS_DIR}/{topic_hash}.txt"
    return pdf_path, txt_path


class SavePaperTextTool(Tool):
    """Save parsed paper text to a file."""
    
    @property
    def name(self) -> str:
        return "save_paper_text"
    
    @property
    def description(self) -> str:
        return "Save paper text content to a file, returns the file path"
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "topic": {"type": "string", "description": "Paper topic"},
            "text": {"type": "string", "description": "Full text content"}
        }
    
    async def execute(self, topic: str, text: str, **kwargs) -> str:
        os.makedirs(PAPERS_DIR, exist_ok=True)
        pdf_path, txt_path = paper_storage_paths(topic)
        
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(text)
        
        logger.info(f"Saved paper text: {txt_path} ({len(text)} chars)")
        
        return json.dumps({
            "txt_path": txt_path,
            "pdf_path": pdf_path,
            "text_length": len(text)
        })


class ReadPaperTextTool(Tool):
    """Read previously saved paper text from file."""
    
    @property
    def name(self) -> str:
        return "read_paper_text"
    
    @property
    def description(self) -> str:
        return "Read full text content from a paper TXT file"
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "txt_path": {"type": "string", "description": "Path to TXT file"}
        }
    
    async def execute(self, txt_path: str, **kwargs) -> str:
        if not os.path.exists(txt_path):
            return f"Error: File not found - {txt_path}"
        
        with open(txt_path, "r", encoding="utf-8") as f:
            text = f.read()
        
        logger.info(f"Read paper text: {txt_path} ({len(text)} chars)")
        return text  # Return full text, no truncation


class ExtractKnowledgePointsTool(Tool):
    """Extract knowledge points from paper text with 6-element structure."""
    
    @property
    def name(self) -> str:
        return "extract_knowledge_points"
    
    @property
    def description(self) -> str:
        return "Extract structured knowledge points from paper text using 6-element model"
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "paper_text": {"type": "string", "description": "Full paper text"},
            "topic": {"type": "string", "description": "Paper topic"},
            "parent_topic": {"type": "string", "description": "Parent summary topic"}
        }
    
    async def execute(self, paper_text: str, topic: str, parent_topic: str, **kwargs) -> str:
        # Phase 1: LLM overview → identify knowledge points list
        # Phase 2: For each KP, locate paragraph → 6-element extraction
        # Phase 3: Return structured JSON
        # TODO: Implement LLM-based extraction
        return json.dumps({"knowledge_points": [], "status": "not_implemented"})


class ExtractFormulasTool(Tool):
    """Extract mathematical formulas from text sections."""
    
    @property
    def name(self) -> str:
        return "extract_formulas"
    
    @property
    def description(self) -> str:
        return "Extract mathematical formulas from PDF pages or text sections"
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "txt_path": {"type": "string", "description": "Path to TXT file"},
            "sections": {
                "type": "array",
                "items": {"type": "object"},
                "description": "List of {start_line, end_line} to process"
            }
        }
    
    async def execute(self, txt_path: str, sections: list = None, **kwargs) -> str:
        # Phase 1: Detect math-dense paragraphs from text
        # Phase 2: For math-dense sections, extract formulas
        # Phase 3: Return formula list [{"formula": "LaTeX", "context": "...", "page": N}]
        # TODO: Implement regex + LLM vision extraction
        return json.dumps({"formulas": [], "status": "not_implemented"})