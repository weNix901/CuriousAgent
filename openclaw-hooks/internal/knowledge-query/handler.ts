const CA_API = process.env.CA_API_URL || 'http://localhost:4848';

const handler = async (event: any) => {
  // 1. 严格过滤
  if (event.type !== 'message') return;
  if (!event.context?.content || event.context.content.trim().length < 3) return;
  
  const userMessage = event.context.content.trim();
  const topic = userMessage.slice(0, 80);
  
  // 2. Fire-and-forget + 超时保护
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 1000);
    
    const response = await fetch(
      `${CA_API}/api/knowledge/confidence?topic=${encodeURIComponent(topic)}`,
      {
        headers: {
          "Content-Type": "application/json",
          "X-OpenClaw-Agent-Id": "r1d3",
          "X-OpenClaw-Hook-Name": "knowledge-query",
          "X-OpenClaw-Hook-Event": "message:received",
          "X-OpenClaw-Hook-Type": "internal"
        },
        signal: controller.signal
      }
    );
    clearTimeout(timeout);
    
    if (response.ok) {
      const data = await response.json();
      const confidence = data.result?.confidence || 0;
      
      if (confidence >= 0.85) {
        event.messages.push(
          `[KG Context — 置信度高 ${(confidence * 100).toFixed(0)}%]\n` +
          `KG 有完整知识，可直接回答。`
        );
      } else if (confidence >= 0.6) {
        event.messages.push(
          `[KG Context — 置信度中 ${(confidence * 100).toFixed(0)}%]\n` +
          `KG 有部分知识，建议搜索补充。`
        );
      } else if (confidence >= 0.3) {
        event.messages.push(
          `[KG Context — 置信度低 ${(confidence * 100).toFixed(0)}%]\n` +
          `KG 知识有限，建议搜索后再回答。`
        );
      } else {
        event.messages.push(
          `[KG Context — 无知识]\n` +
          `话题: ${topic}\n` +
          `KG 无此话题知识，需要探索。`
        );
      }
    }
  } catch (err: any) {
    // 3. 静默失败
    console.error(`[knowledge-query] Failed: ${err.message}`);
  }
};

export default handler;