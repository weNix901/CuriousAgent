"""
探索器 - 执行实际的知识探索
"""
import json
import os
import subprocess
from . import knowledge_graph as kg
from .arxiv_analyzer import ArxivAnalyzer
from .llm_client import LLMClient


VALID_EXPLORATION_DEPTHS = {"shallow", "medium", "deep"}


class Explorer:
    """
    探索器职责：
    1. 接收一个好奇心 topic
    2. 执行 web search 或 深度推理
    3. 提炼发现
    4. 更新知识图谱
    """

    def __init__(self, exploration_depth: str = "medium"):
        if exploration_depth not in VALID_EXPLORATION_DEPTHS:
            raise ValueError(f"Invalid exploration_depth '{exploration_depth}'. Must be one of: {', '.join(sorted(VALID_EXPLORATION_DEPTHS))}")
        self.exploration_depth = exploration_depth
        self.bocha_key = os.environ.get("BOCHA_API_KEY", "")

    def _call_bocha_search(self, query: str, count: int = 3) -> list:
        """调用 Bocha Search API - 端点: POST /v1/web-search"""
        if not self.bocha_key:
            return []

        url = "https://api.bochaai.com/v1/web-search"
        payload = {"query": query, "count": count}

        try:
            result = subprocess.run(
                ["curl", "-s", "-X", "POST", url,
                 "-H", f"Authorization: Bearer {self.bocha_key}",
                 "-H", "Content-Type: application/json",
                 "-d", json.dumps(payload)],
                capture_output=True, text=True, timeout=15
            )
            data = json.loads(result.stdout)

            # Bocha 返回格式: {"code": 200, "data": {"webPages": {"value": [...]}}}
            if isinstance(data, dict) and data.get("code") == 200:
                web_pages = data.get("data", {}).get("webPages", {})
                items = web_pages.get("value", [])
                return self._parse_bocha_results(items)
        except Exception:
            pass
        return []

    def _parse_bocha_results(self, items: list) -> list:
        """解析 Bocha Search 返回结果"""
        results = []
        for item in items[:5]:
            if isinstance(item, dict):
                title = item.get("name", "")
                snippet = item.get("snippet", "")
                url = item.get("url", "")
                if title:
                    results.append({
                        "title": str(title)[:150],
                        "snippet": str(snippet)[:400],
                        "url": str(url)
                    })
        return results

    def explore(self, curiosity_item: dict) -> dict:
        """执行一次探索"""
        topic = curiosity_item["topic"]

        kg.update_curiosity_status(topic, "investigating")

        layer_result = self._explore_layers(topic)
        action = layer_result.get("action", "layer_dispatch")
        findings = layer_result["findings"]
        sources = layer_result["sources"]

        score = curiosity_item["score"]
        threshold = kg.DEFAULT_STATE["config"]["notification_threshold"]
        should_notify = score >= threshold

        kg.add_knowledge(
            topic=topic,
            depth=int(curiosity_item.get("depth", 5)),
            summary=findings[:300],
            sources=sources
        )
        kg.update_curiosity_status(topic, "done")
        kg.log_exploration(topic, action, findings, should_notify)

        return {
            "topic": topic,
            "action": action,
            "findings": findings,
            "sources": sources,
            "notified": should_notify,
            "score": score
        }

    def _explore_layers(self, topic: str) -> dict:
        """Dispatch to appropriate layers based on exploration_depth"""
        layer_results = {}
        all_sources = []
        actions = []

        # Layer 1: Always runs
        l1_result = self._layer1_search(topic)
        layer_results["layer1"] = l1_result
        all_sources.extend(l1_result["sources"])
        actions.append("layer1_search")

        # Layer 2: medium/deep depth
        if self.exploration_depth in ("medium", "deep"):
            arxiv_links = l1_result.get("arxiv_links", [])
            if arxiv_links:
                l2_result = self._layer2_arxiv(topic, arxiv_links)
                layer_results["layer2"] = l2_result
                all_sources.extend(l2_result["sources"])
                actions.append("layer2_arxiv")

        # Layer 3: deep depth only
        if self.exploration_depth == "deep" and "layer2" in layer_results:
            papers = layer_results["layer2"].get("papers", [])
            if papers:
                l3_result = self._layer3_insights(topic, papers)
                layer_results["layer3"] = l3_result
                all_sources.extend(l3_result["sources"])
                actions.append("layer3_insights")

        # Synthesize findings from all layers
        findings = self._synthesize_findings(topic, layer_results)
        
        return {
            "findings": findings,
            "sources": list(set(all_sources)),
            "action": "+".join(actions)
        }

    def _layer1_search(self, topic: str) -> dict:
        """Layer 1: Web search (always runs)"""
        search_results = self._call_bocha_search(topic)
        
        # Extract arXiv links from search results
        arxiv_links = []
        for result in search_results:
            url = result.get("url", "")
            if "arxiv.org" in url:
                arxiv_links.append(url)
        
        if search_results:
            findings = self._synthesize_web_results(topic, search_results)
            sources = [r["url"] for r in search_results if r.get("url")]
            return {
                "findings": findings,
                "sources": sources,
                "arxiv_links": arxiv_links[:5],  # Max 5 arxiv links
                "search_results": search_results
            }
        findings = self._deep_inference(topic)
        return {"findings": findings, "sources": [], "arxiv_links": [], "search_results": []}

    def _layer2_arxiv(self, topic: str, arxiv_links: list = None) -> dict:
        """Layer 2: ArXiv search (medium/deep depth)"""
        if not arxiv_links:
            return {"findings": "", "sources": [], "papers": []}
        
        analyzer = ArxivAnalyzer()
        result = analyzer.analyze_papers(topic, arxiv_links)
        
        papers = result.get("papers", [])
        sources = [f"https://arxiv.org/abs/{p['arxiv_id']}" for p in papers if p.get("arxiv_id")]
        
        # Build findings from paper analysis
        findings_parts = []
        for paper in papers:
            findings_parts.append(f"论文: {paper.get('title', 'N/A')}")
            findings_parts.append(f"相关性: {paper.get('relevance_score', 0):.2f}")
            if paper.get("key_findings"):
                findings_parts.append("关键发现: " + "; ".join(paper["key_findings"][:3]))
            findings_parts.append("")
        
        return {
            "findings": "\n".join(findings_parts) if findings_parts else "",
            "sources": sources,
            "papers": papers,
            "papers_analyzed": result.get("papers_analyzed", 0),
            "high_relevance_count": result.get("high_relevance_count", 0)
        }

    def _layer3_insights(self, topic: str, papers: list = None) -> dict:
        """Layer 3: Deep insights synthesis (deep depth only)"""
        if not papers or len(papers) < 2:
            return {"findings": "", "sources": []}
        
        client = LLMClient()
        result = client.generate_insights(topic, papers)
        
        return {
            "findings": result.get("insights", ""),
            "sources": [],
            "status": result.get("status", "unknown"),
            "model": result.get("model", "minimax-m2.7")
        }

    def _synthesize_web_results(self, topic: str, results: list) -> str:
        """综合搜索结果，提炼发现"""
        synthesis = [f"关于「{topic}」的核心发现："]
        seen = set()
        for i, r in enumerate(results[:3], 1):
            snippet = r["snippet"]
            if snippet[:100] not in seen:
                seen.add(snippet[:100])
                synthesis.append(f"\n{i}. **{r['title']}**")
                synthesis.append(f"   {snippet[:250]}")
        synthesis.append(f"\n（共 {len(results)} 条相关结果）")
        return "".join(synthesis)

    def _synthesize_findings(self, topic: str, layer_results: dict) -> str:
        """综合各层发现为最终报告"""
        parts = []
        
        # Layer 1: Web search findings
        if "layer1" in layer_results:
            l1 = layer_results["layer1"]
            if l1.get("findings"):
                parts.append("【搜索发现】")
                parts.append(l1["findings"])
        
        # Layer 2: ArXiv analysis
        if "layer2" in layer_results:
            l2 = layer_results["layer2"]
            if l2.get("findings"):
                parts.append("\n【论文分析】")
                parts.append(l2["findings"])
        
        # Layer 3: LLM insights
        if "layer3" in layer_results:
            l3 = layer_results["layer3"]
            if l3.get("findings"):
                parts.append("\n【深度洞察】")
                parts.append(l3["findings"])
        
        return "\n".join(parts) if parts else ""

    def _extract_sources(self, layer_results: dict) -> list:
        """提取所有来源 URL 并去重"""
        sources = []
        
        # Layer 1 sources
        if "layer1" in layer_results:
            sources.extend(layer_results["layer1"].get("sources", []))
        
        # Layer 2 arXiv links
        if "layer2" in layer_results:
            sources.extend(layer_results["layer2"].get("sources", []))
        
        # Deduplicate and limit
        return list(dict.fromkeys(sources))[:10]

    def _deep_inference(self, topic: str) -> str:
        """无搜索结果时的深度推理"""
        state = kg.get_state()
        related = []
        topic_lower = topic.lower()
        for t, v in state["knowledge"]["topics"].items():
            if t.lower() in topic_lower or any(kw in topic_lower for kw in t.lower().split()):
                if v.get("summary"):
                    related.append(f"- {t}: {v['summary'][:100]}")

        parts = [f"推理分析：「{topic}」\n相关已有知识："]
        parts.extend(related[:5] if related else ["- 暂无直接相关知识，标记为深度未知"])
        parts.extend([
            "\n初步推断：",
            "- 该领域与 Agent 自主意识研究高度相关",
            "- 建议通过 web 搜索获取最新资料",
        ])
        return "\n".join(parts)

    def format_for_user(self, result: dict) -> str:
        """格式化探索结果，用于飞书通知"""
        level = "🔥" if result["score"] >= 8 else "💡"
        icon = "🔍" if result["action"] == "web_search" else "🤔"

        msg = [
            f"{level} **好奇心探索报告** {icon}",
            "",
            f"**主题**: {result['topic']}",
            f"**方式**: {result['action']} | **好奇心指数**: {result['score']}",
            "",
            "---",
            result["findings"],
        ]
        if result["sources"]:
            msg.append("")
            msg.append("📚 **来源**:")
            for s in result["sources"][:3]:
                if s:
                    msg.append(f"- {s}")
        return "\n".join(msg)
