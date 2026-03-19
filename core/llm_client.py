"""
LLM Client - Layer 3 洞察生成

使用 minimax API 生成论文对比洞察
"""
import os
from typing import List, Dict, Optional

import requests


class LLMClient:
    """
    minimax LLM 客户端
    
    职责：
    1. 调用 minimax API 生成论文对比洞察
    2. 处理 API 错误和超时
    3. 格式化输出
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("MINIMAX_API_KEY", "")
        self.api_url = "https://api.minimax.chat/v1/text/chatcompletion_v2"
        self.model = "minimax-m2.7"
        self.timeout = 60
    
    def generate_insights(self, topic: str, papers: List[Dict]) -> Dict:
        """
        生成论文对比洞察
        
        Args:
            topic: 探索主题
            papers: Layer 2 分析的论文列表
            
        Returns:
            洞察结果字典
        """
        if not self.api_key:
            return {
                "status": "error",
                "error": "MINIMAX_API_KEY not configured",
                "insights": ""
            }
        
        if len(papers) < 2:
            return {
                "status": "skipped",
                "reason": "Need at least 2 papers for comparison",
                "insights": ""
            }
        
        try:
            prompt = self._generate_comparison_prompt(topic, papers)
            response = self._call_api(prompt)
            
            return {
                "status": "success",
                "insights": response,
                "papers_compared": len(papers),
                "model": self.model
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "insights": ""
            }
    
    def _generate_comparison_prompt(self, topic: str, papers: List[Dict]) -> str:
        """生成对比分析的 prompt"""
        prompt = f"""你是一位 AI 研究分析专家。请基于以下论文分析，生成深度洞察报告。

研究主题: {topic}

"""
        
        for i, paper in enumerate(papers, 1):
            title = paper.get('title', 'N/A')
            authors = paper.get('authors', [])
            abstract = paper.get('abstract', 'N/A')
            key_findings = paper.get('key_findings', [])
            relevance_score = paper.get('relevance_score', 0)
            
            prompt += f"""论文{i}:
标题: {title}
作者: {', '.join(authors[:3]) if authors else 'N/A'}
摘要: {abstract[:500] if abstract else 'N/A'}...
关键发现: {'; '.join(key_findings[:3]) if key_findings else 'N/A'}
相关性评分: {relevance_score:.2f}

"""
        
        prompt += """请提供以下分析:
1. 方法论对比表（维度：方法类型、创新点、局限性）
2. 核心贡献总结
3. 跨论文趋势观察
4. 对该研究领域的建议
5. 是否值得深入探索（是/否 + 理由）

请以结构化格式输出。"""
        
        return prompt
    
    def _call_api(self, prompt: str) -> str:
        """调用 minimax API"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a helpful research analysis assistant."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.7,
            "max_tokens": 2000
        }
        
        response = requests.post(
            self.api_url,
            headers=headers,
            json=payload,
            timeout=self.timeout
        )
        response.raise_for_status()
        
        data = response.json()
        return data.get("choices", [{}])[0].get("message", {}).get("content", "")
