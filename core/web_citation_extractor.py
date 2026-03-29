"""Web Citation Extractor - Extract external references from web sources."""
import json
import subprocess
from typing import Optional

from core.llm_client import LLMClient


class WebCitationExtractor:
    """
    从网页来源中提取外部引用，转变为 KG 子节点。

    提取策略:
    1. 抓取高权重来源页面的内容（前 3 个）
    2. 使用 LLM 分析页面引用的关键技术/概念
    3. 将提取结果作为子 topic 加入 KG
    """

    MAX_SOURCES = 3
    MAX_CONTENT_LENGTH = 8000

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm = llm_client or LLMClient()

    def extract_from_sources(self, topic: str, sources: list[str]) -> list[dict]:
        """
        从 sources 列表中提取外部引用。

        Args:
            topic: 父 topic 名称
            sources: 来源 URL 列表

        Returns:
            提取到的引用列表，每项包含 name, source_url, reason
        """
        if not sources:
            return []

        citations = []
        for url in sources[:self.MAX_SOURCES]:
            try:
                page_citations = self._extract_from_page(topic, url)
                citations.extend(page_citations)
            except Exception as e:
                print(f"[WebCitationExtractor] Failed to extract from {url}: {e}")
                continue

        # 去重：按 name 去重
        seen = set()
        unique_citations = []
        for c in citations:
            name = c.get("name", "").lower()
            if name and name not in seen:
                seen.add(name)
                unique_citations.append(c)

        return unique_citations

    def _extract_from_page(self, topic: str, url: str) -> list[dict]:
        """
        从单个页面提取引用。

        Args:
            topic: 父 topic
            url: 页面 URL

        Returns:
            引用列表
        """
        # 抓取页面内容
        content = self._fetch_page(url)
        if not content:
            return []

        # 使用 LLM 提取引用的关键技术/概念
        prompt = f"""分析以下网页内容，提取该页面引用的核心技术、方法或框架。

父主题: {topic}
来源 URL: {url}

网页内容:
{content[:self.MAX_CONTENT_LENGTH]}

要求：
1. 找出该页面明确提到的、与"{topic}"相关的技术/方法/框架
2. 每个引用应该是可独立探索的技术概念（如 "Transformer", "BERT", "Self-Attention"）
3. 排除太宽泛的概念（如 "Machine Learning", "AI"）
4. 排除页面自身的标题/品牌名

返回 JSON 格式：
{{
    "citations": [
        {{
            "name": "技术名称",
            "reason": "为什么这个技术与 {topic} 相关（一句话）"
        }},
        ...
    ]
}}

如果只找到 0-1 个相关引用，返回空列表或少量项目。最多返回 5 个。
"""

        try:
            response = self.llm.chat(prompt, temperature=0.3)
            return self._parse_citations(response, url)
        except Exception as e:
            print(f"[WebCitationExtractor] LLM extraction failed for {url}: {e}")
            return []

    def _fetch_page(self, url: str) -> str:
        """
        抓取页面内容，返回文本。

        使用 curl 获取页面，然后用简单逻辑提取正文。
        """
        try:
            result = subprocess.run(
                ["curl", "-s", "-L", "--max-time", "10", "-A",
                 "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                 url],
                capture_output=True, text=True, timeout=15
            )
            html = result.stdout

            # 简单提取：移除 script/style 标签，提取文本
            import re
            # 移除 script 和 style
            html = re.sub(r'<script[^>]*>.*?</script>', ' ', html, flags=re.DOTALL | re.IGNORECASE)
            html = re.sub(r'<style[^>]*>.*?</style>', ' ', html, flags=re.DOTALL | re.IGNORECASE)
            # 移除 HTML 标签
            text = re.sub(r'<[^>]+>', ' ', html)
            # 合并空白
            text = re.sub(r'\s+', ' ', text).strip()

            return text[:self.MAX_CONTENT_LENGTH]
        except Exception as e:
            print(f"[WebCitationExtractor] Fetch failed for {url}: {e}")
            return ""

    def _parse_citations(self, response: str, source_url: str) -> list[dict]:
        """解析 LLM 响应，提取引用列表。"""
        try:
            # 尝试解析 JSON
            json_match = self._extract_json(response)
            if json_match:
                data = json.loads(json_match)
                citations = data.get("citations", [])
                # 添加 source_url
                for c in citations:
                    c["source_url"] = source_url
                return citations
        except json.JSONDecodeError as e:
            print(f"[WebCitationExtractor] JSON parse failed: {e}")

        # Fallback：尝试从文本中提取
        return self._parse_fallback(response, source_url)

    def _extract_json(self, text: str) -> Optional[str]:
        """从文本中提取 JSON 块。"""
        import re
        # 找 {...} 块
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            return match.group(0)
        return None

    def _parse_fallback(self, text: str, source_url: str) -> list[dict]:
        """Fallback 解析：从文本行中提取。"""
        citations = []
        import re

        # 找 "- name: ..." 或 "- name ..." 或 "name: ..." 格式
        lines = text.split('\n')
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            # 匹配 "- name" 或 "name:" 后的内容
            match = re.match(r'^[\-\*]?\s*(?:name\s*[:\-]\s*)?([^\-\*\n]{3,50})$', line)
            if match:
                name = match.group(1).strip()
                if name and len(name) > 3:
                    citations.append({
                        "name": name,
                        "reason": f"Referenced in {source_url}",
                        "source_url": source_url
                    })

        return citations[:5]  # 最多 5 个
