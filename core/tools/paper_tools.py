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