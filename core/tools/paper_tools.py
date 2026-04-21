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