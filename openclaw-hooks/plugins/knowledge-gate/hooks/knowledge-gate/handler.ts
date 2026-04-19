const CA_API = process.env.CA_API_URL || 'http://localhost:4848';

const COMMON_HEADERS = {
  "Content-Type": "application/json",
  "X-OpenClaw-Agent-Id": "r1d3",
  "X-OpenClaw-Hook-Name": "knowledge-gate",
  "X-OpenClaw-Hook-Event": "message",
  "X-OpenClaw-Hook-Type": "plugin_sdk",
};

async function queryKG(topic: string): Promise<any> {
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 1000);

    const response = await fetch(
      `${CA_API}/api/knowledge/check`,
      {
        method: 'POST',
        headers: COMMON_HEADERS,
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
      { headers: COMMON_HEADERS, signal: controller.signal }
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

// 外层 try/catch — 绝不阻断 agent 回复
export const beforeAgentReplyHook = async ({ context }: any) => {
  try {
    if (context.agentId !== 'researcher') return;

    const topic = extractTopic(context);
    if (!topic) return;

    // 并发查询（Promise.allSettled 不抛异常），超时会自动 abort
    const [kgResult, confResult] = await Promise.allSettled([
      queryKG(topic),
      queryConfidence(topic)
    ]);

    const contextParts: string[] = [];

    // 安全提取 — Promise.allSettled 可能返回 rejected
    const kgData = kgResult.status === 'fulfilled' ? kgResult.value : null;
    const confData = confResult.status === 'fulfilled' ? confResult.value : null;
    const confidence = kgData?.result?.confidence || 0;

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

    if (confData?.confidence_high != null && confData?.confidence_low != null) {
      const avgConf = (confData.confidence_high + confData.confidence_low) / 2;
      if (avgConf < 0.6) {
        contextParts.push(`[探索状态] 该话题置信度 ${(avgConf * 100).toFixed(0)}%，仍在完善中。`);
      }
    }

    if (contextParts.length > 0) {
      context.additionalContext = (context.additionalContext || '') + '\n\n' + contextParts.join('\n\n');
    }
  } catch (err: any) {
    // 绝不 throw — 静默失败
    console.error(`[knowledge-gate] Failed: ${err.message}`);
  }
};
