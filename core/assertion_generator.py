# core/assertion_generator.py
"""Generate and validate knowledge assertions from findings"""
import re
from typing import List, Dict


class AssertionGenerator:
    """
    Generate atomic knowledge assertions from exploration findings.
    
    Uses LLM to extract verifiable facts and filters low-quality assertions.
    """
    
    MIN_LENGTH = 15
    MAX_LENGTH = 200
    
    BANNED_PREFIXES = [
        "this paper", "this article", "this study", "this research",
        "the paper", "the article", "the study", "the research",
        "this explores", "this discusses", "this presents",
        "this is about", "we discuss", "we present"
    ]
    
    def __init__(self, llm_client):
        self.llm = llm_client
    
    def generate(self, topic: str, findings: Dict, 
                 num_assertions: int = 3) -> List[str]:
        """
        Generate validated assertions from findings.
        
        Args:
            topic: The exploration topic
            findings: Dict with 'summary', 'sources', 'papers'
            num_assertions: Number of assertions to generate
            
        Returns:
            List of high-quality assertions
        """
        raw_assertions = self._generate_raw(topic, findings, num_assertions)
        validated = [a for a in raw_assertions if self._validate(a, topic)]
        
        print(f"[AssertionGenerator] Generated {len(validated)}/{len(raw_assertions)} valid assertions")
        return validated
    
    def _generate_raw(self, topic: str, findings: Dict, 
                      num_assertions: int) -> List[str]:
        
        prompt = f"""你是知识工程师。从以下探索结果中提取{num_assertions}个具体、可验证的知识断言。

Topic: "{topic}"

探索摘要:
{findings.get('summary', '')[:1000]}

来源标题:
{[s.get('title', '') for s in findings.get('sources', [])[:3]]}

论文标题:
{[p.get('title', '') for p in findings.get('papers', [])[:3]]}

任务要求:
1. 每个断言必须是原子知识陈述（主语+谓语+宾语）
2. 断言不能只是topic名称的重复或改写
3. 断言必须具体可验证（能在知识库中查到）
4. 禁止元评论（如"这篇论文讲的是..."）

正确示例:
- "Mamba uses selective state spaces for O(N) inference"
- "RLHF aligns models using PPO algorithm"
- "Transformer attention has O(N²) complexity"

错误示例:
- "Mamba is a topic" （太泛）
- "This paper discusses Mamba" （元评论）
- "Mamba" （只是名称）

输出格式: 每行一个断言，不要编号，不要解释。"""

        try:
            response = self.llm.chat(prompt)
            return self._parse_assertions(response)
        except Exception as e:
            print(f"[AssertionGenerator] LLM error: {e}")
            return []
    
    def _parse_assertions(self, response: str) -> List[str]:
        assertions = []
        
        for line in response.split('\n'):
            line = line.strip()
            
            if not line:
                continue
            
            if re.match(r'^\d+[.\)]\s*', line):
                line = re.sub(r'^\d+[.\)]\s*', '', line)
            
            if line.startswith('- ') or line.startswith('* '):
                line = line[2:]
            
            line = line.strip()
            
            if line:
                assertions.append(line)
        
        return assertions
    
    def _validate(self, assertion: str, topic: str) -> bool:
        """
        Validate assertion quality.
        
        Checks:
        - Length constraints
        - Banned prefixes (meta-commentary)
        - Topic repetition
        """
        if len(assertion) < self.MIN_LENGTH:
            return False
        
        if len(assertion) > self.MAX_LENGTH:
            return False
        
        lower_assertion = assertion.lower()
        for prefix in self.BANNED_PREFIXES:
            if lower_assertion.startswith(prefix):
                return False
        
        topic_words = set(topic.lower().split())
        assertion_words = set(lower_assertion.split())
        
        if topic_words:
            overlap = len(topic_words & assertion_words) / len(topic_words)
            if overlap > 0.8 and len(assertion) < len(topic) * 1.5:
                return False
        
        return True
