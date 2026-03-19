"""
探索器 - 执行实际的知识探索
"""
import json
import os
import subprocess
from . import knowledge_graph as kg


class Explorer:
    """
    探索器职责：
    1. 接收一个好奇心 topic
    2. 执行 web search 或 深度推理
    3. 提炼发现
    4. 更新知识图谱
    """

    def __init__(self):
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

        # Step 1: Web Search
        search_results = self._call_bocha_search(topic)

        if search_results:
            action = "web_search"
            findings = self._synthesize_findings(topic, search_results)
        else:
            # Step 2: Fallback → 深度推理
            action = "inference"
            findings = self._deep_inference(topic)

        # Step 3: 是否通知用户
        score = curiosity_item["score"]
        threshold = kg.DEFAULT_STATE["config"]["notification_threshold"]
        should_notify = score >= threshold

        # Step 4: 更新知识图谱
        sources = [r["url"] for r in search_results if r.get("url")]
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

    def _synthesize_findings(self, topic: str, results: list) -> str:
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
