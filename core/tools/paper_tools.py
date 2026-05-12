# core/tools/paper_tools.py
"""Paper processing tools for Curious Agent v0.3.3."""
import hashlib
import os
import json
import re
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
        # Phase 1: LLM overview → identify 5-15 candidate knowledge points
        candidates = await self._phase1_overview(paper_text, topic, parent_topic)
        
        if not candidates:
            return json.dumps({"knowledge_points": [], "status": "no_candidates_found"})
        
        # Phase 2: For each candidate (max 12), extract 6-element structure
        knowledge_points = []
        for candidate in candidates[:12]:
            kp = await self._extract_6_element(candidate, paper_text)
            if kp:
                knowledge_points.append(kp)
        
        return json.dumps({
            "knowledge_points": knowledge_points,
            "status": "success"
        })
    
    def _call_llm_with_fallback(self, prompt: str) -> str | None:
        """Call LLM with provider fallback: volcengine → minimax."""
        from core.llm_client import LLMClient
        
        for provider in ["volcengine", "minimax"]:
            try:
                client = LLMClient(provider_name=provider)
                response = client.chat(prompt)
                if response and response.strip():
                    return response
            except Exception as e:
                logger.warning(f"LLM call failed with provider={provider}: {e}")
                continue
        
        logger.error("All LLM providers failed")
        return None
    
    def _parse_json_response(self, response: str, expect_array: bool = False) -> Any:
        """Parse JSON from LLM response with regex fallback."""
        # Primary: direct json.loads
        try:
            return json.loads(response)
        except (json.JSONDecodeError, ValueError):
            pass
        
        # Fallback: regex extraction
        try:
            if expect_array:
                match = re.search(r'\[\s*\{.*?\}\s*\]', response, re.DOTALL)
            else:
                match = re.search(r'\{\s*"topic".*?\}', response, re.DOTALL)
            
            if match:
                return json.loads(match.group())
        except (json.JSONDecodeError, AttributeError):
            pass
        
        return None
    
    async def _phase1_overview(self, paper_text: str, topic: str, parent_topic: str) -> list[dict]:
        """Phase 1: LLM overview to identify 5-15 candidate knowledge points."""
        truncated = paper_text[:12000]
        
        prompt = f"""You are a knowledge extraction expert. Analyze the following academic paper text and identify 5-15 key knowledge points.

Topic: {topic}
Parent Topic: {parent_topic}

For each knowledge point, identify:
- topic: The name/title of the knowledge point
- source_section: Which section of the paper it comes from
- relevance_score: A score from 0.0 to 1.0 indicating relevance to the main topic

Return ONLY a JSON array of objects with this exact structure:
[
  {{"topic": "Knowledge Point Name", "source_section": "Section Name", "relevance_score": 0.9}},
  ...
]

Paper text:
---
{truncated}
---"""
        
        response = self._call_llm_with_fallback(prompt)
        if not response:
            logger.warning("Phase 1 LLM call failed, returning no candidates")
            return []
        
        candidates = self._parse_json_response(response, expect_array=True)
        if not isinstance(candidates, list):
            logger.warning(f"Phase 1 returned non-array: {type(candidates)}")
            return []
        
        # Validate and filter candidates
        valid_candidates = []
        for c in candidates:
            if isinstance(c, dict) and "topic" in c and "source_section" in c:
                valid_candidates.append({
                    "topic": str(c.get("topic", "")),
                    "source_section": str(c.get("source_section", "")),
                    "relevance_score": float(c.get("relevance_score", 0.5))
                })
        
        logger.info(f"Phase 1 identified {len(valid_candidates)} candidates")
        return valid_candidates
    
    def _locate_paragraphs(self, paper_text: str, topic: str, section_hint: str, max_chars: int = 2000) -> str:
        """Locate relevant paragraphs using keyword matching."""
        paragraphs = paper_text.split("\n\n")
        
        # Extract keywords from topic + section_hint (words > 3 chars)
        keywords = []
        for text in [topic, section_hint]:
            words = re.findall(r'[a-zA-Z\u4e00-\u9fff]{4,}', text)
            keywords.extend([w.lower() for w in words])
        
        if not keywords:
            # Fallback: return first few paragraphs
            combined = "\n\n".join(paragraphs[:5])
            return combined[:max_chars]
        
        # Score each paragraph by keyword matches
        scored = []
        for para in paragraphs:
            para_lower = para.lower()
            score = sum(1 for kw in keywords if kw in para_lower)
            if score > 0:
                scored.append((score, para))
        
        # Sort by score descending, take top 5
        scored.sort(key=lambda x: x[0], reverse=True)
        top_paragraphs = [p for _, p in scored[:5]]
        
        if not top_paragraphs:
            combined = "\n\n".join(paragraphs[:5])
        else:
            combined = "\n\n".join(top_paragraphs)
        
        return combined[:max_chars]
    
    async def _extract_6_element(self, candidate: dict, paper_text: str) -> dict | None:
        """Phase 2: Extract 6-element structure for a single candidate."""
        topic = candidate["topic"]
        section_hint = candidate.get("source_section", "")
        
        # Locate relevant paragraphs
        context_text = self._locate_paragraphs(paper_text, topic, section_hint)
        
        prompt = f"""Extract a structured knowledge point from the following text.

Knowledge Point Topic: {topic}
Section Hint: {section_hint}

Extract the following 6 elements:
- definition: A concise 1-2 sentence definition
- core: The core principle or mechanism
- context: Background, who proposed it, when, why
- examples: Concrete usage examples or applications
- formula: Mathematical expressions (empty string if none)
- relationships: Related concepts, parent/sibling concepts

Return ONLY a JSON object with this exact structure:
{{
  "definition": "...",
  "core": "...",
  "context": "...",
  "examples": "...",
  "formula": "",
  "relationships": "..."
}}

Context text:
---
{context_text}
---"""
        
        response = self._call_llm_with_fallback(prompt)
        if not response:
            logger.warning(f"Phase 2 LLM call failed for candidate: {topic}")
            return None
        
        result = self._parse_json_response(response, expect_array=False)
        if not isinstance(result, dict):
            logger.warning(f"Phase 2 returned non-object for candidate: {topic}")
            return None
        
        # Build the 6-element knowledge point
        fields = {
            "definition": str(result.get("definition", "")).strip(),
            "core": str(result.get("core", "")).strip(),
            "context": str(result.get("context", "")).strip(),
            "examples": str(result.get("examples", "")).strip(),
            "formula": str(result.get("formula", "")).strip(),
            "relationships": str(result.get("relationships", "")).strip()
        }
        
        completeness = self._calc_completeness(fields)
        
        return {
            "topic": topic,
            "source_section": section_hint,
            "relevance_score": candidate.get("relevance_score", 0.5),
            "definition": fields["definition"],
            "core": fields["core"],
            "context": fields["context"],
            "examples": fields["examples"],
            "formula": fields["formula"],
            "relationships": fields["relationships"],
            "completeness_score": completeness
        }
    
    def _calc_completeness(self, fields: dict) -> float:
        """Calculate completeness score based on non-empty fields."""
        scored_fields = ["definition", "core", "context", "examples", "formula"]
        non_empty = 0
        for f in scored_fields:
            val = fields.get(f)
            if val is None:
                continue
            # Handle both string and list types
            if isinstance(val, list):
                if len(val) > 0:
                    non_empty += 1
            elif isinstance(val, str):
                if val.strip() and val != "N/A":
                    non_empty += 1
        return round(non_empty / len(scored_fields), 2)


class ExtractFormulasTool(Tool):
    """Extract mathematical formulas from text sections."""

    # Unicode math symbols for density detection
    MATH_SYMBOLS = set(
        "∑∫∂√±≤≥≠∈∝∞αβγδεθλμπσφω+-*/=^_"
    )
    MATH_DENSITY_THRESHOLD = 0.01
    MAX_MATH_PARAGRAPHS = 5

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

    async def execute(self, txt_path: str, sections: list | None = None, **kwargs) -> str:
        if not os.path.exists(txt_path):
            return json.dumps({"formulas": [], "status": "file_not_found", "error": f"File not found: {txt_path}"})

        with open(txt_path, "r", encoding="utf-8") as f:
            text = f.read()

        if not text.strip():
            return json.dumps({"formulas": [], "status": "no_math_content"})

        # Phase 1: Split into paragraphs and detect math-dense ones
        paragraphs = text.split("\n\n")
        math_dense_paragraphs = []

        for idx, para in enumerate(paragraphs):
            if self._is_math_dense(para):
                math_dense_paragraphs.append((idx, para))

        if not math_dense_paragraphs:
            logger.info("No math-dense paragraphs found in %s", txt_path)
            return json.dumps({"formulas": [], "status": "no_math_content"})

        # Limit to max 5 math-dense paragraphs
        math_dense_paragraphs = math_dense_paragraphs[:self.MAX_MATH_PARAGRAPHS]
        logger.info("Found %d math-dense paragraphs in %s (processing %d)",
                     len(math_dense_paragraphs), txt_path, len(math_dense_paragraphs))

        # Phase 2: Extract formulas from each math-dense paragraph
        all_formulas = []
        for para_idx, para_text in math_dense_paragraphs:
            formulas = await self._extract_formulas_from_section(para_text, para_idx)
            all_formulas.extend(formulas)

        logger.info("Extracted %d formulas from %s", len(all_formulas), txt_path)

        return json.dumps({
            "formulas": all_formulas,
            "status": "success"
        })

    def _is_math_dense(self, paragraph: str) -> bool:
        """Check if a paragraph has high math symbol density (>1%)."""
        if not paragraph.strip():
            return False

        math_count = sum(1 for char in paragraph if char in self.MATH_SYMBOLS)
        total_chars = len(paragraph)

        if total_chars == 0:
            return False

        density = math_count / total_chars
        return density > self.MATH_DENSITY_THRESHOLD

    async def _extract_formulas_from_section(self, paragraph: str, para_index: int) -> list[dict]:
        """Extract LaTeX formulas from a math-dense paragraph using LLM."""
        prompt = f"""You are a mathematical formula extraction expert. Analyze the following text and extract ALL mathematical formulas.

For each formula found, provide:
- formula: The LaTeX representation of the formula
- context: A brief description of what the formula represents or where it's used
- source_location: "paragraph_{para_index}"

Return ONLY a JSON array of objects with this exact structure:
[
  {{"formula": "E = mc^2", "context": "Einstein's mass-energy equivalence", "source_location": "paragraph_{para_index}"}},
  ...
]

If no clear formulas are found, return an empty array: []

Text:
---
{paragraph}
---"""

        response = self._call_llm_with_fallback(prompt)
        if not response:
            logger.warning("LLM call failed for paragraph %d", para_index)
            return []

        formulas = self._parse_json_response(response, expect_array=True)
        if not isinstance(formulas, list):
            logger.warning("Non-array response for paragraph %d: %s", para_index, type(formulas))
            return []

        # Validate and normalize results
        valid_formulas = []
        for item in formulas:
            if isinstance(item, dict) and "formula" in item:
                valid_formulas.append({
                    "formula": str(item.get("formula", "")).strip(),
                    "context": str(item.get("context", "")).strip(),
                    "source_location": str(item.get("source_location", f"paragraph_{para_index}")).strip()
                })

        logger.info("Extracted %d formulas from paragraph %d", len(valid_formulas), para_index)
        return valid_formulas

    def _call_llm_with_fallback(self, prompt: str) -> str | None:
        """Call LLM with provider fallback: volcengine → minimax."""
        from core.llm_client import LLMClient

        for provider in ["volcengine", "minimax"]:
            try:
                client = LLMClient(provider_name=provider)
                response = client.chat(prompt)
                if response and response.strip():
                    return response
            except Exception as e:
                logger.warning("LLM call failed with provider=%s: %s", provider, e)
                continue

        logger.error("All LLM providers failed")
        return None

    def _parse_json_response(self, response: str, expect_array: bool = False) -> Any:
        """Parse JSON from LLM response with regex fallback."""
        # Primary: direct json.loads
        try:
            return json.loads(response)
        except (json.JSONDecodeError, ValueError):
            pass

        # Fallback: regex extraction
        try:
            if expect_array:
                match = re.search(r'\[\s*\{.*?\}\s*\]', response, re.DOTALL)
            else:
                match = re.search(r'\{\s*".*?".*?\}', response, re.DOTALL)

            if match:
                return json.loads(match.group())
        except (json.JSONDecodeError, AttributeError):
            pass

        return None