"""
LLM Client - Compatible interface, delegates to LLMManager

Backward compatible interface that delegates to LLMManager
"""
import os
from typing import List, Dict, Optional


class LLMClient:
    """
    Backward-compatible LLMClient that delegates to LLMManager
    """
    
    def __init__(self, api_key: Optional[str] = None, provider_name: Optional[str] = None, model_name: Optional[str] = None):
        """
        Initialize LLMClient.
        
        Args:
            api_key: Deprecated, kept for backward compatibility
            provider_name: Override provider selection
            model_name: Override model selection
        """
        from core.llm_manager import LLMManager
        from core.config import get_config
        
        # Load config and initialize LLMManager if not already initialized
        config = get_config()
        llm_config = {
            "providers": {},
            "selection_strategy": "capability"
        }
        for p in config.llm_providers:
            llm_config["providers"][p.name] = {
                "api_url": p.api_url,
                "timeout": p.timeout,
                "enabled": p.enabled,
                "models": [
                    {"model": m.model, "weight": m.weight, "capabilities": m.capabilities, "max_tokens": m.max_tokens}
                    for m in p.models
                ]
            }
        
        self.manager = LLMManager.get_instance(llm_config)
        self.provider_override = provider_name
        self.model_override = model_name
        # Backward compatibility attributes
        self.api_key = api_key or os.environ.get("MINIMAX_API_KEY") or os.environ.get("VOLCENGINE_API_KEY", "")
        self.model = os.environ.get("VOLCENGINE_MODEL", "minimax-m2.7")
        self.timeout = 60
    
    def chat(self, prompt: str, **kwargs) -> str:
        """Send chat request"""
        return self.manager.chat(
            prompt,
            task_type="general",
            provider_override=self.provider_override,
            model_override=self.model_override,
            **kwargs
        )
    
    def generate_insights(self, topic: str, papers: List[Dict], **kwargs):
        """Generate paper insights (Layer 3)"""
        prompt = self._build_insight_prompt(topic, papers)
        return self.manager.chat(
            prompt,
            task_type="insights",
            provider_override=self.provider_override,
            model_override=self.model_override,
            **kwargs
        )
    
    def _build_insight_prompt(self, topic: str, papers: List[Dict]) -> str:
        """Build insight prompt"""
        parts = [f"研究主题: {topic}\n\n"]
        for i, paper in enumerate(papers, 1):
            parts.append(f"论文{i}: {paper.get('title', 'N/A')}\n")
            parts.append(f"摘要: {paper.get('abstract', '')[:300]}...\n")
            parts.append(f"关键发现: {', '.join(paper.get('key_findings', [])[:3])}\n\n")
        parts.append("请提供深度洞察报告，包括：\n")
        parts.append("1. 主要研究趋势\n")
        parts.append("2. 各论文之间的关系\n")
        parts.append("3. 对实际应用的建议\n")
        return "".join(parts)
    
    def evaluate_intrinsic_signals(self, topic: str, findings: dict) -> dict:
        """Evaluate intrinsic signals (for ICM)"""
        prompt = f"""Evaluate the intrinsic signals (0-10 scale) for the following exploration:

Topic: {topic}
Findings: {findings.get('summary', '')[:500]}

Return JSON format:
{{
  "pred_error": <prediction error score>,
  "graph_density": <graph density score>,
  "novelty": <novelty score>
}}

Scoring criteria:
- pred_error: higher score means larger prediction error (worth exploring)
- graph_density: higher score means fewer connections (isolated knowledge)
- novelty: higher score means less overlap with known knowledge"""
        
        import json
        try:
            response = self.manager.chat(
                prompt,
                task_type="icm_signals",
                provider_override=self.provider_override,
                model_override=self.model_override
            )
            start = response.find('{')
            end = response.rfind('}')
            if start >= 0 and end > start:
                return json.loads(response[start:end+1])
        except Exception as e:
            print(f"[LLMClient] Error evaluating signals: {e}")
        
        return {"pred_error": 5.0, "graph_density": 5.0, "novelty": 5.0}

    # === Backward compatibility methods ===

    def _call_api(self, prompt: str) -> str:
        """Legacy API call method - delegates to manager"""
        try:
            return self.chat(prompt)
        except ValueError as e:
            if "No available LLM providers" in str(e):
                return f"[LLMClient] No providers configured for prompt: {prompt[:50]}..."
            raise

    def _generate_comparison_prompt(self, topic: str, papers: List[Dict]) -> str:
        """Legacy prompt generation - use _build_insight_prompt instead"""
        prompt_parts = [f"""You are an AI research analysis expert. Generate a deep insights report based on the following paper analysis.

Research Topic: {topic}

"""]
        
        for i, paper in enumerate(papers, 1):
            title = paper.get('title', 'N/A')
            authors = paper.get('authors', [])
            abstract = paper.get('abstract', 'N/A')
            key_findings = paper.get('key_findings', [])
            relevance_score = paper.get('relevance_score', 0)
            
            prompt_parts.append(f"""Paper {i}:
Title: {title}
Authors: {', '.join(authors[:3]) if authors else 'N/A'}
Abstract: {abstract[:500] if abstract else 'N/A'}...
Key Findings: {'; '.join(key_findings[:3]) if key_findings else 'N/A'}
Relevance Score: {relevance_score:.2f}

""")
        
        prompt_parts.append("""Please provide the following analysis:
1. Methodology comparison table (dimensions: method type, innovation, limitations)
2. Summary of core contributions
3. Cross-paper trend observations
4. Recommendations for the research field
5. Whether it's worth exploring in depth (yes/no + reason)

Please output in a structured format.""")
        
        return "".join(prompt_parts)
