"""
arXiv 论文分析器 - Layer 2 探索
"""
import os
import re
import tempfile
from typing import Optional, List, Dict

import requests

try:
    import arxiv
except ImportError:
    arxiv = None

try:
    from PyPDF2 import PdfReader
except ImportError:
    PdfReader = None


class ArxivAnalyzer:
    """
    arXiv 论文分析器
    
    职责：
    1. 从 arXiv URL 提取论文元数据
    2. 计算与探索主题的相关性
    3. 下载并解析有价值的论文
    """
    
    def __init__(self):
        self.temp_dir = tempfile.gettempdir()
        self.relevance_threshold = 0.3  # 放宽相关性门槛
    
    def analyze_papers(self, topic: str, arxiv_links: List[str]) -> Dict:
        """
        分析一组 arXiv 论文（带容错和 fallback）
        
        Args:
            topic: 探索主题
            arxiv_links: arXiv URL 列表
            
        Returns:
            分析结果字典
        """
        results = []
        
        for link in arxiv_links[:5]:  # 最多分析 5 篇
            arxiv_id = self._extract_arxiv_id(link)
            if not arxiv_id:
                continue
            
            try:
                paper = self._fetch_arxiv_metadata(arxiv_id)
                if not paper:
                    # Fallback: 构造伪论文对象
                    paper = self._build_fallback_paper(arxiv_id, topic)
                
                relevance_score = self.compute_relevance(topic, paper)
                
                analysis = {
                    "arxiv_id": arxiv_id,
                    "title": paper.get("title", ""),
                    "authors": paper.get("authors", []),
                    "abstract": paper.get("abstract", ""),
                    "relevance_score": relevance_score,
                    "published": paper.get("published", ""),
                    "primary_category": paper.get("primary_category", ""),
                    "downloaded_full": False,
                    "full_text_preview": "",
                    "is_fallback": paper.get("is_fallback", False)
                }
                
                if relevance_score > self.relevance_threshold:
                    full_text = self._download_and_extract(arxiv_id)
                    if full_text:
                        analysis["downloaded_full"] = True
                        analysis["full_text_preview"] = full_text[:2000]
                        analysis["key_findings"] = self._extract_key_findings(full_text)
                
                results.append(analysis)
                
            except Exception as e:
                print(f"Error analyzing arxiv:{arxiv_id}: {e}")
                # 即使出错也添加 fallback
                fallback = self._build_fallback_paper(arxiv_id, topic)
                fallback["relevance_score"] = 0.5  # 默认中等相关性
                results.append(fallback)
                continue
        
        return {
            "papers_analyzed": len(results),
            "papers": results,
            "high_relevance_count": sum(1 for p in results if p["relevance_score"] > self.relevance_threshold)
        }
    
    def _build_fallback_paper(self, arxiv_id: str, topic: str) -> Dict:
        """构造伪论文对象（当获取失败时使用）"""
        return {
            "title": f"Paper about {topic}",
            "authors": [],
            "abstract": f"arXiv paper {arxiv_id} on {topic} (fallback)",
            "published": "",
            "primary_category": "",
            "pdf_url": f"https://arxiv.org/pdf/{arxiv_id}.pdf",
            "is_fallback": True
        }
    
    def _extract_arxiv_id(self, url: str) -> Optional[str]:
        """从 URL 中提取 arXiv ID"""
        patterns = [
            r"arxiv\.org/abs/(\d+\.\d+)",
            r"arxiv\.org/pdf/(\d+\.\d+)\.pdf",
            r"arxiv:(\d+\.\d+)"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        return None
    
    def _fetch_arxiv_metadata(self, arxiv_id: str) -> Optional[Dict]:
        """获取 arXiv 论文元数据（使用 arxiv 库）"""
        if arxiv is None:
            return None
            
        try:
            client = arxiv.Client()
            search = arxiv.Search(id_list=[arxiv_id])
            paper = next(client.results(search), None)
            
            if paper:
                return {
                    "title": paper.title,
                    "authors": [str(a) for a in paper.authors],
                    "abstract": paper.summary,
                    "published": str(paper.published),
                    "primary_category": paper.primary_category,
                    "pdf_url": paper.pdf_url
                }
        except Exception as e:
            print(f"Error fetching arxiv metadata: {e}")
        
        return None
    
    def compute_relevance(self, topic: str, paper: Dict) -> float:
        """
        计算论文与主题的相关性评分
        
        算法：基于词频的加权评分
        - 标题匹配权重：60%
        - 摘要匹配权重：40%
        """
        topic_words = set(topic.lower().split())
        
        if not topic_words:
            return 0.0
        
        title = paper.get("title", "").lower()
        abstract = paper.get("abstract", "").lower()
        
        title_matches = len(topic_words & set(title.split()))
        abstract_matches = len(topic_words & set(abstract.split()))
        
        title_score = title_matches / len(topic_words)
        abstract_score = abstract_matches / (len(topic_words) * 3)
        abstract_score = min(abstract_score, 1.0)
        
        return title_score * 0.6 + abstract_score * 0.4
    
    def _download_and_extract(self, arxiv_id: str, retries: int = 2) -> Optional[str]:
        """下载 PDF 并提取文本（前2页），带重试机制"""
        pdf_path = os.path.join(self.temp_dir, f"{arxiv_id}.pdf")
        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
        
        for attempt in range(retries + 1):
            try:
                if not os.path.exists(pdf_path):
                    response = requests.get(pdf_url, timeout=10)
                    response.raise_for_status()
                    
                    with open(pdf_path, "wb") as f:
                        f.write(response.content)
                
                return self._extract_pdf_text(pdf_path, pages=2)
                
            except requests.Timeout:
                print(f"Timeout downloading {arxiv_id}, attempt {attempt + 1}/{retries + 1}")
                if attempt < retries:
                    import time
                    time.sleep(1)
                continue
            except Exception as e:
                print(f"Error downloading/extracting PDF: {e}")
                return None
        
        return None
    
    def _extract_pdf_text(self, pdf_path: str, pages: int = 2) -> Optional[str]:
        """使用 PyPDF2 提取 PDF 文本"""
        if PdfReader is None:
            return None
            
        try:
            reader = PdfReader(pdf_path)
            text = ""
            
            for i, page in enumerate(reader.pages):
                if i >= pages:
                    break
                text += page.extract_text() + "\n"
            
            return text.strip()
            
        except Exception as e:
            print(f"Error extracting PDF text: {e}")
            return None
    
    def _extract_key_findings(self, text: str) -> List[str]:
        """从文本中提取关键发现（简单启发式）"""
        findings = []
        
        keywords = ["contribution", "propose", "method", "result", "conclusion"]
        sentences = text.split(".")
        
        for sentence in sentences[:20]:
            sentence_lower = sentence.lower()
            for keyword in keywords:
                if keyword in sentence_lower and len(sentence) > 20:
                    findings.append(sentence.strip())
                    break
            
            if len(findings) >= 3:
                break
        
        return findings
