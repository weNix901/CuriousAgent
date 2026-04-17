const CA_API = process.env.CA_API_URL || 'http://localhost:4848';

const LOW_CONFIDENCE_PATTERNS = [
  "基于 LLM 知识", "我猜测", "不太确定",
  "了解一些但不完全", "Based on my LLM knowledge",
  "我猜测可能是", "基于猜测", "可能", "大概"
];

const handler = async (event: any) => {
  if (event.type !== 'message') return;
  
  const replyContent = event.context?.content;
  if (!replyContent || replyContent.trim().length < 10) return;
  
  // 检测低置信度
  const isLowConfidence = LOW_CONFIDENCE_PATTERNS.some(p => replyContent.includes(p));
  if (!isLowConfidence) return;
  
  const topic = replyContent.trim().slice(0, 80);
  
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 1000);
    
    await fetch(`${CA_API}/api/knowledge/learn`, {
      method: 'POST',
      headers: {
        "Content-Type": "application/json",
        "X-OpenClaw-Agent-Id": "r1d3",
        "X-OpenClaw-Hook-Name": "knowledge-learn",
        "X-OpenClaw-Hook-Event": "message:sent",
        "X-OpenClaw-Hook-Type": "internal"
      },
      body: JSON.stringify({
        topic,
        context: replyContent.slice(0, 500),
        strategy: 'llm_answer'
      }),
      signal: controller.signal
    });
    
    clearTimeout(timeout);
    console.log(`[knowledge-learn] Injected: ${topic}`);
  } catch (err: any) {
    console.error(`[knowledge-learn] Failed: ${err.message}`);
  }
};

export default handler;