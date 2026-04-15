"""
Paper Citation Extractor — 从论文中提取核心引用，转变为 KG 子节点

方案 A: LLM 直接分析论文摘要/标题，提取引用的技术/框架
方案 B: PDF 解析，识别 Related Work / References 段落，提取真实引用
去重: 两个方案的结果合并去重
"""
import logging
import os
import re
import tempfile
from typing import Optional

import requests

logger = logging.getLogger(__name__)

try:
    import arxiv as arxiv_lib
except ImportError:
    arxiv_lib = None

try:
    from PyPDF2 import PdfReader
except ImportError:
    PdfReader = None

from core.llm_client import LLMClient


# ============ 方案 A: LLM 分析 ============

CITATION_EXTRACT_PROMPT = """你是一个学术论文分析助手。

你的任务：从给定论文的信息中，识别该论文 Related Work 或引言部分提到的核心技术、框架、方法。

论文标题: {title}
论文摘要: {abstract}

要求：
1. 找出论文在 Related Work / Introduction 中明确引用的关键技术或框架
2. 只返回真实存在的、被论文引用的技术，不是你自己补充的
3. 格式：技术名称 (作者, 年份) 或 技术名称
4. 每项一行，如：
   - Attention Is All You Need (Vaswani et al., 2017)
   - Residual Networks (He et al., 2016)
   - BERT (Devlin et al., 2019)
5. 如果没有明确的引用技术，返回"无"

只返回引用列表，不要其他解释。"""


# ============ 方案 B: PDF 解析 ============

# 识别 References / Bibliography 段落的正则
REF_SECTION_PATTERNS = [
    r"References\s*\n",
    r"References\s*$",
    r"Bibliography\s*\n",
    r"References and Bibliography\s*\n",
]

# 识别单条引用的正则（常见格式）
CITATION_PATTERNS = [
    # "Author, Title, Conference, Year"
    r"([A-Z][a-z]+(?:\s+(?:et\s+al\.?|[A-Z][a-z]+))?)\s*[,.\s]+(.+?)\s*[,.\s]+\((\d{4})\)?",
    # "[N] Author (Year)"
    r"\[\d+\]\s*([A-Z][a-z]+(?:\s+(?:et\s+al\.?))?)\s*\((\d{4})\)[,.\s]+(.+?)(?:\.|,|$)",
    # "Author [Year]"
    r"([A-Z][a-z]+(?:\s+(?:et\s+al\.?))?)\s*\[(\d{4})\]\s*[,.]\s*(.+?)(?:\.|;|$)",
]

# 技术/框架名称的关键词（用于快速过滤）
TECH_KEYWORDS = [
    "attention", "transformer", "bert", "gpt", "lstm", "cnn", "resnet",
    "reinforcement learning", "policy", "reward", "gradient",
    "neural", "network", "embedding", "encoder", "decoder",
    "memory", "retrieval", "search", "ranking",
    "optimization", "optimizer", "adam", "sgd",
    "layer normalization", "batch normalization", "dropout",
    "cross attention", "self-attention", "multi-head",
    "knowledge graph", "graph neural", "gnn",
    "prompt", "few-shot", "zero-shot", "fine-tuning",
    "rlhf", "ppo", "actor-critic", "ddpg",
    "ddn", "vae", "gan", "diffusion",
]


def _looks_like_tech_reference(text: str) -> bool:
    """快速判断一段文本是否像技术引用"""
    text_lower = text.lower()
    return any(kw in text_lower for kw in TECH_KEYWORDS)


def _extract_year(text: str) -> str:
    """从文本中提取年份"""
    match = re.search(r"\b(19|20)\d{2}\b", text)
    return match.group() if match else ""


# ============ PaperCitationExtractor ============

class PaperCitationExtractor:
    """
    从论文中提取核心引用

    策略：
    1. 方案 A: LLM 分析摘要/标题（轻量，永远执行）
    2. 方案 B: PDF 解析 References 段落（重量，只对高相关论文执行）
    3. 去重: 两个方案的结果按技术名称去重
    """

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm = llm_client or LLMClient()
        self.temp_dir = tempfile.gettempdir()
        self.max_papers_for_pdf = 3  # PDF 解析消耗大，最多解析 3 篇

    def extract_all(self, topic: str, papers: list[dict]) -> list[dict]:
        """
        完整流程：方案 A + 方案 B + 去重

        Args:
            topic: 父 topic 名称
            papers: arxiv_analyzer 返回的论文列表

        Returns:
            去重后的引用列表 [{"name": "...", "source_paper": "...", "year": "..."}, ...]
        """
        if not papers:
            return []

        citations = []

        # 方案 A: LLM 分析所有论文（轻量）
        llm_citations = self._extract_via_llm(papers)
        citations.extend(llm_citations)
        print(f"[CitationExtractor] LLM extracted {len(llm_citations)} citations")

        # 方案 B: PDF 解析高相关论文（重量，最多 3 篇）
        high_relevance = [p for p in papers if p.get("relevance_score", 0) > 0.5]
        for paper in high_relevance[: self.max_papers_for_pdf]:
            pdf_citations = self._extract_via_pdf(paper)
            if pdf_citations:
                citations.extend(pdf_citations)
                print(f"[CitationExtractor] PDF extracted {len(pdf_citations)} from {paper.get('arxiv_id')}")

        # 去重
        deduplicated = self._deduplicate(citations)
        print(f"[CitationExtractor] Total: {len(citations)}, Deduplicated: {len(deduplicated)}")

        return deduplicated

    def _extract_via_llm(self, papers: list[dict]) -> list[dict]:
        """方案 A: LLM 分析摘要/标题"""
        citations = []

        for paper in papers:
            title = paper.get("title", "")
            abstract = paper.get("abstract", "")[:1000]  # 截断避免 token 过多

            if not title and not abstract:
                continue

            prompt = CITATION_EXTRACT_PROMPT.format(title=title, abstract=abstract)

            try:
                response = self.llm.chat(prompt, temperature=0.1)
                parsed = self._parse_llm_response(response)
                for name in parsed:
                    citations.append({
                        "name": name,
                        "source_paper": title,
                        "source_arxiv_id": paper.get("arxiv_id", ""),
                        "method": "llm",
                        "year": _extract_year(name)
                    })
            except Exception as e:
                print(f"[CitationExtractor] LLM failed for '{title}': {e}")

        return citations

    def _parse_llm_response(self, response: str) -> list[str]:
        """解析 LLM 返回的引用列表"""
        results = []
        for line in response.strip().split("\n"):
            line = line.strip()
            if not line or line in ("无", "无引用", "无相关引用", "None", "N/A"):
                continue
            # 去掉 "- " 前缀
            if line.startswith("-"):
                line = line[1:].strip()
            # 去掉 "[N]" 编号前缀
            line = re.sub(r"^\[\d+\]\s*", "", line)
            # 去掉 URL 尾巴
            if "http" in line.lower():
                line = re.sub(r"https?://\S+$", "", line).strip()
            if line and len(line) > 3:
                results.append(line)
        return results

    def _extract_via_pdf(self, paper: dict) -> list[dict]:
        """方案 B: PDF 解析 References 段落"""
        arxiv_id = paper.get("arxiv_id", "")
        if not arxiv_id:
            return []

        pdf_text = self._download_and_extract_references(arxiv_id)
        if not pdf_text:
            return []

        return self._parse_references_text(pdf_text, paper)

    def _download_and_extract_references(self, arxiv_id: str, pages: int = 8) -> Optional[str]:
        """下载 PDF，提取 References 段落的文本"""
        pdf_path = os.path.join(self.temp_dir, f"{arxiv_id}_ref.pdf")
        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"

        try:
            if not os.path.exists(pdf_path):
                response = requests.get(pdf_url, timeout=15)
                response.raise_for_status()
                with open(pdf_path, "wb") as f:
                    f.write(response.content)
        except Exception as e:
            print(f"[CitationExtractor] PDF download failed for {arxiv_id}: {e}")
            return None

        if PdfReader is None:
            return None

        try:
            reader = PdfReader(pdf_path)
            # 只读前 8 页（References 通常在前几页）
            text = ""
            for i, page in enumerate(reader.pages):
                if i >= pages:
                    break
                text += page.extract_text() + "\n"
            return text
        except Exception as e:
            print(f"[CitationExtractor] PDF extract failed for {arxiv_id}: {e}")
            return None

    def _parse_references_text(self, text: str, paper: dict) -> list[dict]:
        """从 References 段落中提取技术引用"""
        citations = []

        # 找到 References 段落
        ref_start = -1
        for pattern in REF_SECTION_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                ref_start = match.start()
                break

        if ref_start == -1:
            return []

        ref_text = text[ref_start:]

        # 分割成单条引用（粗略按换行分段）
        lines = ref_text.split("\n")
        buffer = ""

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 如果行以大写字母开头+年份，可能是新引用
            is_new_ref = bool(re.match(r"^\[[\d]+\]?\s*[A-Z]", line)) or \
                         bool(re.match(r"^[A-Z][a-z]+(?:\s+(?:et\s+al\.?))?\s*\[?\d{4}\]?", line))

            if is_new_ref and buffer:
                # 处理上一条
                if _looks_like_tech_reference(buffer):
                    parsed = self._extract_tech_from_citation(buffer)
                    for name in parsed:
                        citations.append({
                            "name": name,
                            "source_paper": paper.get("title", ""),
                            "source_arxiv_id": paper.get("arxiv_id", ""),
                            "method": "pdf",
                            "year": _extract_year(name)
                        })
                buffer = line
            else:
                buffer += " " + line

        # 处理最后一条
        if buffer and _looks_like_tech_reference(buffer):
            parsed = self._extract_tech_from_citation(buffer)
            for name in parsed:
                citations.append({
                    "name": name,
                    "source_paper": paper.get("title", ""),
                    "source_arxiv_id": paper.get("arxiv_id", ""),
                    "method": "pdf",
                    "year": _extract_year(name)
                })

        return citations

    def _extract_tech_from_citation(self, citation_text: str) -> list[str]:
        """从单条引用文本中提取技术名称"""
        results = []

        # 用 LLM 做二次提取（从原始引用文本中识别技术名称）
        prompt = f"""从以下学术引用文本中，提取提到的技术、框架或方法名称。

引用文本：
{citation_text[:500]}

要求：
- 只提取真实被引用的技术/框架/方法名
- 不要提取作者名字本身
- 格式：技术名称 (作者, 年份)

示例输入："Attention is All You Need. Vaswani et al. 2017."
示例输出：- Attention Is All You Need (Vaswani et al., 2017)

只返回识别出的技术列表，每行一条。"""

        try:
            response = self.llm.chat(prompt, temperature=0.1)
            parsed = self._parse_llm_response(response)
            results.extend(parsed)
        except Exception as e:
            logger.warning(f"Failed to extract tech from citation: {e}", exc_info=True)

        # 备用：正则直接提（作者 年份）格式
        fallback = re.findall(r"([A-Z][a-zA-Z\s]+(?:Is|All|of|For|The)\s+[A-Z][a-zA-Z\s]+?)\s*\(?[A-Z][a-z]+(?:\s+et\s+al\.?)?,?\s*(\d{4})\)?", citation_text)
        for name, year in fallback:
            name = name.strip()
            if name and len(name) > 4 and _looks_like_tech_reference(name):
                results.append(f"{name} ({year})")

        return results

    def _deduplicate(self, citations: list[dict]) -> list[dict]:
        """按技术名称去重，优先保留 LLM 结果（更准确）"""
        seen = {}
        for c in citations:
            # 归一化名称用于比较（去掉括号里的年份、去掉大小写差异）
            normalized = re.sub(r"\s*\(\D+?\s*\d{4}\)\s*", "", c["name"]).strip().lower()
            normalized = re.sub(r"\s+", " ", normalized)

            if normalized not in seen:
                seen[normalized] = c
            else:
                # 如果已有，但新的是 LLM 方法，保留 LLM 版本
                if c.get("method") == "llm" and seen[normalized].get("method") == "pdf":
                    seen[normalized] = c

        return list(seen.values())

