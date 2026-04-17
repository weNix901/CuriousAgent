const CA_API = process.env.CA_API_URL || 'http://localhost:4848';

const COMMON_HEADERS = {
  "Content-Type": "application/json",
  "X-OpenClaw-Agent-Id": "r1d3",
  "X-OpenClaw-Hook-Name": "knowledge-gate",
  "X-OpenClaw-Hook-Event": "message",
  "X-OpenClaw-Hook-Type": "internal",
};

async function queryKG(topic: string): Promise<any> {
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 1000);
    const response = await fetch(`${CA_API}/api/knowledge/check`, {
      method: 'POST',
      headers: COMMON_HEADERS,
      body: JSON.stringify({ topic }),
      signal: controller.signal,
    });
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
      { headers: COMMON_HEADERS, signal: controller.signal }
    );
    clearTimeout(timeout);
    return response.ok ? await response.json() : null;
  } catch {
    return null;
  }
}

const handler = async (event: any) => {
  if (event.type !== 'message') return;
  if (!event.context?.content || event.context.content.trim().length < 3) return;

  const topic = event.context.content.trim().slice(0, 80);

  try {
    const [kgResult, confResult] = await Promise.all([
      queryKG(topic),
      queryConfidence(topic),
    ]);

    const parts: string[] = [];
    if (kgResult?.result?.found && kgResult.result.confidence >= 0.6) {
      parts.push(
        `[KG Context — 置信度高 ${(kgResult.result.confidence * 100).toFixed(0)}%]\n` +
        `${kgResult.result.summary || 'KG 中有相关知识。'}`
      );
    } else if (kgResult?.result?.confidence > 0) {
      parts.push(
        `[KG Context — 置信度中 ${(kgResult.result.confidence * 100).toFixed(0)}%]\n` +
        `KG 有部分知识，建议搜索补充。`
      );
    }
    if (confResult?.result?.confidence !== undefined) {
      const c = confResult.result.confidence;
      if (c > 0 && c < 0.6) {
        parts.push(`[探索状态] 该话题置信度 ${(c * 100).toFixed(0)}%，仍在完善中。`);
      }
    }
    if (parts.length > 0) {
      event.messages.push(parts.join('\n\n'));
    }
  } catch (err: any) {
    console.error(`[knowledge-gate] Failed: ${err.message}`);
  }
};

export default handler;