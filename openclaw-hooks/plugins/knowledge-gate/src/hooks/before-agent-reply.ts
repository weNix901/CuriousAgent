const CA_API = process.env.CA_API_URL || 'http://localhost:4848';

async function queryKG(topic: string): Promise<any> {
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 1000);
    
    const response = await fetch(
      `${CA_API}/api/knowledge/check`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic }),
        signal: controller.signal
      }
    );
    
    clearTimeout(timeout);
    return response.ok ? await response.json() : null;
  } catch {
    return null;
  }
}

async function queryConfidence(topic: string): Promise<any> {
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 1000);
    
    const response = await fetch(
      `${CA_API}/api/kg/confidence/${encodeURIComponent(topic)}`,
      { signal: controller.signal }
    );
    
    clearTimeout(timeout);
    return response.ok ? await response.json() : null;
  } catch {
    return null;
  }
}

function extractTopic(context: any): string {
  const messages = context.messages || [];
  for (let i = messages.length - 1; i >= 0; i--) {
    if (messages[i].role === 'user' && messages[i].content) {
      return messages[i].content.trim().slice(0, 80);
    }
  }
  return '';
}

export const beforeAgentReplyHook = async ({ context }: any) => {
  if (context.agentId !== 'researcher') return;
  
  const topic = extractTopic(context);
  if (!topic) return;
  
  const kgResult = await queryKG(topic);
  const confResult = await queryConfidence(topic);
  
  const contextParts: string[] = [];
  
  const confidence = kgResult?.result?.confidence || 0;
  
  if (confidence >= 0.85) {
    contextParts.push(
      `[KG Context — 置信度高 ${(confidence * 100).toFixed(0)}%]\n` +
      `KG 有完整知识。`
    );
  } else if (confidence >= 0.6) {
    contextParts.push(
      `[KG Context — 置信度中 ${(confidence * 100).toFixed(0)}%]\n` +
      `KG 有部分知识，建议搜索补充。`
    );
  } else if (confidence > 0) {
    contextParts.push(
      `[KG Context — 置信度低 ${(confidence * 100).toFixed(0)}%]\n` +
      `KG 知识有限。`
    );
  }
  
  if (confResult?.confidence_high && confResult?.confidence_low) {
    const avgConf = (confResult.confidence_high + confResult.confidence_low) / 2;
    if (avgConf < 0.6) {
      contextParts.push(`[探索状态] 该话题置信度 ${(avgConf * 100).toFixed(0)}%，仍在完善中。`);
    }
  }
  
  if (contextParts.length > 0) {
    context.additionalContext = (context.additionalContext || '') + '\n\n' + contextParts.join('\n\n');
  }
};