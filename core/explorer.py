"""
探索器 - 执行实际的知识探索
"""
import json
import os
import subprocess
from . import knowledge_graph as kg
from .arxiv_analyzer import ArxivAnalyzer
from .llm_client import LLMClient
from .insight_synthesizer import InsightSynthesizer
from .paper_citation_extractor import PaperCitationExtractor
from .web_citation_extractor import WebCitationExtractor


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

    def _call_serper_search(self, query: str, count: int = 3) -> list:
        """调用 Serper Google Search API - Bocha 失效时的备用"""
        serper_key = os.environ.get("SERPER_API_KEY", "5ab85d954a1d224281498b13b8d4731f05e1d562")
        url = "https://google.serper.dev/search"
        payload = {"q": query, "numResults": count}

        try:
            result = subprocess.run(
                ["curl", "-s", "-X", "POST", url,
                 "-H", f"X-API-KEY: {serper_key}",
                 "-H", "Content-Type: application/json",
                 "-d", json.dumps(payload)],
                capture_output=True, text=True, timeout=30
            )
            data = json.loads(result.stdout)
            if isinstance(data, dict) and "organic" in data:
                return self._parse_serper_results(data["organic"])
        except Exception:
            pass
        return []

    def _parse_serper_results(self, items: list) -> list:
        """解析 Serper Google Search 返回结果"""
        results = []
        for item in items[:5]:
            if isinstance(item, dict):
                title = item.get("title", "")
                snippet = item.get("snippet", "")
                link = item.get("link", "")
                if title:
                    results.append({
                        "title": str(title)[:150],
                        "snippet": str(snippet)[:400],
                        "url": str(link)
                    })
        return results

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

        # v0.2.6 fix: 如果所有层都没有返回有效内容，
        # 仍然写入 KG（标记为 no_content），但不产生 stub。
        if not findings or len(findings) < 20:
            print(f"[Explorer] No valid content for '{topic}' after all layers, saving with no_content status")
            kg.add_knowledge(
                topic=topic,
                depth=int(curiosity_item.get("depth", 5)),
                summary="[no web content found - niche topic or search failed]",
                sources=sources
            )
            kg.update_curiosity_status(topic, "no_content")
            kg.log_exploration(topic, action, findings, False)
            return {
                "topic": topic,
                "action": action,
                "findings": "[no web content found - niche topic or search failed]",
                "sources": [],
                "notified": False,
                "score": 0
            }

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

        # ===== T-12 集成点 开始 =====
        # 【集成点 7】Explorer 集成 Layer 3 — InsightSynthesizer
        sub_topics = curiosity_item.get("sub_topics")
        if sub_topics and self.exploration_depth in ("medium", "deep"):
            try:
                synthesizer = InsightSynthesizer(llm_client=self.llm_client)
                # Build sub_topic_results from layer_results
                sub_topic_results = {}
                for st in sub_topics:
                    st_name = st.get("sub_topic", st.get("topic", "unknown"))
                    layer1_data = layer_result.get(st_name, [])
                    if layer1_data:
                        sub_topic_results[st_name] = layer1_data

                if sub_topic_results:
                    insights = synthesizer.synthesize(topic, sub_topic_results)
                    layer_result["insights"] = insights
                    print(f"[T-12] Layer 3 generated {len(insights)} insights for {topic}")
            except Exception as e:
                print(f"[T-12] InsightSynthesizer failed: {e}")
        # ===== T-12 集成点 结束 =====

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

        # === v0.2.6 Fix #4: 提取网页引用 ===
        if l1_result.get("sources") and self.exploration_depth in ("medium", "deep"):
            try:
                web_extractor = WebCitationExtractor()
                web_citations = web_extractor.extract_from_sources(topic, l1_result["sources"])
                for citation in web_citations:
                    name = citation.get("name", "")
                    if not name or len(name) > 100:
                        continue
                    kg.add_child(topic, name)
                    kg.add_curiosity(
                        topic=name,
                        reason=f"Web citation: {citation.get('reason', '')}",
                        relevance=6.0,
                        depth=5.0,
                        original_topic=topic,
                        topic_type="web_citation"
                    )
                if web_citations:
                    print(f"[Explorer] Extracted {len(web_citations)} web citations for '{topic}'")
            except Exception as e:
                print(f"[Explorer] Web citation extraction failed: {e}")
        # === v0.2.6 结束 ===

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
        """Layer 1: Web search (always runs) - Serper 优先，Bocha 备用

        v0.2.6 fix: 完整的探索保证 - 永不产生 stub。
        策略：多轮查询增强 + 多 Provider 链式降级 + stub 模式检测。
        """
        import time

        # ===== 预检查：太短的 topics 直接标记为失败，不产生 stub =====
        if len(topic.strip()) < 3:
            print(f"[Explorer] Topic '{topic}' too short for search, marking as failed (no stub)")
            return {"findings": "", "sources": [], "arxiv_links": [], "search_results": [], "status": "failed_too_short"}

        # ===== 生成多轮查询策略 =====
        queries = self._generate_query_variants(topic)
        all_results = []
        used_queries = set()

        # ===== 链式搜索：每个查询都尝试 Serper + Bocha =====
        for query in queries:
            if query in used_queries:
                continue
            used_queries.add(query)

            # Serper
            results = self._call_serper_search(query)
            if results:
                all_results.extend(results)
                print(f"[Explorer] Serper got {len(results)} results for '{query}'")

            # Bocha (补充)
            bocha_results = self._call_bocha_search(query)
            if bocha_results:
                # 去重
                existing_urls = {r.get("url") for r in all_results}
                for br in bocha_results:
                    if br.get("url") not in existing_urls:
                        all_results.append(br)
                if bocha_results:
                    print(f"[Explorer] Bocha补充 {len(bocha_results)} results for '{query}'")

            # 如果已经有足够的结果（>= 5），可以提前停止
            if len(all_results) >= 5:
                print(f"[Explorer] Got {len(all_results)} total results, stopping search")
                break

            # 避免 API 限流
            time.sleep(0.5)

        # ===== 去重 =====
        seen_urls = set()
        deduped = []
        for r in all_results:
            url = r.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                deduped.append(r)
        all_results = deduped

        # ===== 提取 arXiv 链接 =====
        arxiv_links = [r.get("url") for r in all_results if "arxiv.org" in r.get("url", "")]

        # ===== 如果没有任何结果：标记失败，不产生 stub =====
        if not all_results:
            print(f"[Explorer] All queries failed for '{topic}', marking exploration as failed (no stub)")
            return {"findings": "", "sources": [], "arxiv_links": [], "search_results": [], "status": "search_failed"}

        # ===== 合成内容 =====
        findings = self._synthesize_web_results(topic, all_results)

        # ===== Stub 模式检测 =====
        stub_patterns = ["推理分析：", "相关已有知识", "初步推断", "该领域与 Agent 自主意识"]
        is_stub = any(pattern in findings for pattern in stub_patterns)
        is_too_short = len(findings) < 150

        if is_stub or is_too_short:
            print(f"[Explorer] Content check failed for '{topic}': stub={is_stub}, short={is_too_short} ({len(findings)} chars)")
            # 再试一组更具体的查询
            retry_queries = [
                f"{topic} research paper 2024 2025",
                f"{topic} deep learning neural network",
                f"what is {topic} AI machine learning",
            ]
            for retry_q in retry_queries:
                if retry_q in used_queries:
                    continue
                used_queries.add(retry_q)
                retry_results = self._call_serper_search(retry_q)
                if retry_results:
                    all_results.extend(retry_results)
                    print(f"[Explorer] Retry query '{retry_q}' got {len(retry_results)} results")
                time.sleep(0.5)

            # 重新合成
            seen_urls = set()
            deduped = []
            for r in all_results:
                url = r.get("url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    deduped.append(r)
            all_results = deduped
            arxiv_links = [r.get("url") for r in all_results if "arxiv.org" in r.get("url", "")]
            findings = self._synthesize_web_results(topic, all_results)

            # 最终检查：如果还是 stub，返回空（不产生噪音）
            is_stub = any(pattern in findings for pattern in stub_patterns)
            if is_stub or len(findings) < 150:
                print(f"[Explorer] Retry also produced stub/short content for '{topic}', returning empty (no stub)")
                return {"findings": "", "sources": [], "arxiv_links": [], "search_results": [], "status": "content_too_poor"}

        sources = [r["url"] for r in all_results if r.get("url")]
        print(f"[Explorer] Successfully synthesized {len(findings)} chars of content for '{topic}'")
        return {
            "findings": findings,
            "sources": sources,
            "arxiv_links": arxiv_links[:5],
            "search_results": all_results,
            "status": "success"
        }

    def _generate_query_variants(self, topic: str) -> list:
        """v0.2.6: 为 topic 生成多个查询变体，按优先级排序"""
        queries = [topic]  # 原始查询优先

        # 如果 topic 是单字或很通用，添加增强变体
        broad_keywords = {
            "agent", "model", "system", "learning", "network", "memory",
            "planning", "control", "task", "reasoning", "attention",
            "reward", "policy", "state", "action", "goal", "curiosity"
        }
        topic_lower = topic.lower().strip()
        is_generic = topic_lower in broad_keywords or len(topic_lower.split()) <= 1

        if is_generic:
            # 通用词需要更具体的上下文
            queries.extend([
                f"{topic} AI artificial intelligence agent",
                f"{topic} machine learning deep learning",
                f"{topic} autonomous agent LLM",
            ])
        else:
            # 正常 topic 的变体
            queries.extend([
                f"{topic} research 2024 2025",
                f"{topic} deep learning neural network",
            ])

        return queries

    def _layer2_arxiv(self, topic: str, arxiv_links: list = None) -> dict:
        """Layer 2: ArXiv search (medium/deep depth)"""
        if not arxiv_links:
            return {"findings": "", "sources": [], "papers": []}
        
        analyzer = ArxivAnalyzer()
        result = analyzer.analyze_papers(topic, arxiv_links)
        
        papers = result.get("papers", [])

        # === v0.2.6: 提取论文引文，写入 cites 边 ===
        if papers:
            try:
                extractor = PaperCitationExtractor()
                citations = extractor.extract_all(topic, papers)
                for c in citations:
                    name = c.get("name", "")
                    if not name or len(name) > 100:
                        continue
                    kg.add_citation(topic, name)
                    kg.add_curiosity(
                        topic=name,
                        reason=f"Cited by: {topic}",
                        relevance=7.0,
                        depth=5.0,
                        original_topic=topic,
                        topic_type="citation"
                    )
                if citations:
                    print(f"[Explorer] Extracted {len(citations)} citations from papers for '{topic}'")
            except Exception as e:
                print(f"[Explorer] Citation extraction failed: {e}")
        # === v0.2.6 结束 ===

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
            snippet = r.get("snippet", "").strip()
            # v0.2.6 fix: Skip results with empty or very short snippets
            # (often indicates search returned generic/navigation results)
            if len(snippet) < 30:
                continue
            # Deduplicate by snippet content
            snippet_key = snippet[:100]
            if snippet_key in seen:
                continue
            seen.add(snippet_key)
            synthesis.append(f"\n{i}. **{r['title']}**")
            synthesis.append(f"   {snippet[:300]}")
        synthesis.append(f"\n（共 {len(results)} 条相关结果）")
        result = "".join(synthesis)
        # v0.2.6 fix: Always return something if we had search results, even if many were filtered
        # The header "关于「X」的核心发现：\n（共 N 条相关结果）" is valid content
        return result

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
        """无搜索结果时的深度推理

        v0.2.6 fix: 此方法已废弃，不再产生 stub 内容。
        所有探索路径都已改为：搜索失败 -> 返回空内容 -> 不写入 KG。
        保留此方法仅为兼容，以防其他代码调用。
        """
        # 返回空字符串，不再产生任何 stub 内容
        return ""

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
