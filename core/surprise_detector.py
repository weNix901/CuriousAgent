import json
import re


class SurpriseDetector:
    def __init__(self, llm_client):
        self.llm = llm_client
    
    def generate_assumptions(self, topic: str) -> list[str]:
        """生成3条假设"""
        prompt = f"""关于「{topic}」，请列出3条你认为最可能正确的假设。
每行一条，格式必须为：我以为：<内容>
不要有其他格式，不要编号。"""
        
        try:
            response = self.llm.chat(prompt)
            lines = [l.strip() for l in response.split("\n") if l.strip()]
            assumptions = [l for l in lines if "我以为：" in l]
            return assumptions[:3]
        except Exception as e:
            print(f"[SurpriseDetector] Failed to generate assumptions: {e}")
            return []
    
    def check_surprise(self, findings: dict, assumptions: list[str]) -> dict:
        """检查是否有惊异"""
        if not assumptions:
            return {"is_surprise": False, "surprise_level": 0.0}
        
        findings_text = findings.get("summary", str(findings)[:1000])
        assumptions_text = "\n".join(assumptions)
        
        prompt = f"""给定探索结论：
{findings_text}

检验以下假设是否被推翻或出乎意料：
{assumptions_text}

请仔细判断：
- 如果结论完全符合假设 → is_surprise=false, surprise_level=0.0
- 如果结论部分出乎意料 → is_surprise=true, surprise_level=0.3~0.6
- 如果结论完全出乎意料/颠覆认知 → is_surprise=true, surprise_level=0.7~1.0

输出 JSON（不要有其他内容）：
{{"is_surprise": true/false, "surprise_level": 0.0~1.0}}"""
        
        try:
            response = self.llm.chat(prompt)
            match = re.search(r'\{.*\}', response, re.DOTALL)
            if match:
                return json.loads(match.group())
        except Exception as e:
            print(f"[SurpriseDetector] Failed to check surprise: {e}")
        
        return {"is_surprise": False, "surprise_level": 0.0}
