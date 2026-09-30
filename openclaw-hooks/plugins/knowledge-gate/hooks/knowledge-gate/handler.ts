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
    if (!response.ok) {
      // F3: 失败可观测 —— 不再静默吞掉
      console.error(`[knowledge-gate] /api/knowledge/check HTTP ${response.status}`);
      return null;
    }
    return await response.json();
  } catch (err: any) {
    console.error(`[knowledge-gate] /api/knowledge/check failed: ${err?.message}`);
    return null;
  }
}

// F2 修复：/api/kg/confidence/{topic} 不存在 → 实际端点是 /api/knowledge/confidence?topic=
async function queryConfidence(topic: string): Promise<any> {
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 1000);

    const response = await fetch(
      `${CA_API}/api/knowledge/confidence?topic=${encodeURIComponent(topic)}`,
      { headers: COMMON_HEADERS, signal: controller.signal }
    );

    clearTimeout(timeout);
    if (!response.ok) {
      console.error(`[knowledge-gate] /api/knowledge/confidence HTTP ${response.status}`);
      return null;
    }
    return await response.json();
  } catch (err: any) {
    console.error(`[knowledge-gate] /api/knowledge/confidence failed: ${err?.message}`);
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

    // F2 修复：/api/knowledge/confidence 返回 { result: { confidence, quality, level, ... } }
    // 不再依赖不存在的 confidence_high / confidence_low 字段
    const conf = confData?.result?.confidence;
    if (conf != null && conf < 0.6) {
      contextParts.push(`[探索状态] 该话题置信度 ${(conf * 100).toFixed(0)}%，仍在完善中。`);
    }

    if (contextParts.length > 0) {
      context.additionalContext = (context.additionalContext || '') + '\n\n' + contextParts.join('\n\n');
    }
  } catch (err: any) {
    // 绝不 throw — 但留日志（F3）
    console.error(`[knowledge-gate] Failed: ${err.message}`);
  }
};
