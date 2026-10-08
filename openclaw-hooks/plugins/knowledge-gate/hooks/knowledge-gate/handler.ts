const CA_API = process.env.CA_API_URL || 'http://localhost:4848';

const COMMON_HEADERS = {
  "Content-Type": "application/json",
  "X-OpenClaw-Agent-Id": "r1d3",
  "X-OpenClaw-Hook-Name": "knowledge-gate",
  "X-OpenClaw-Hook-Event": "message",
  "X-OpenClaw-Hook-Type": "plugin_sdk",
};

// C1-C-3 (v0.3.6): 四态查询端点。
// 端点形状经 2026-10-04 实测确认：路径参数 `/api/kg/confidence/<topic>` → 200，
// 而查询串 `?topic=` → 404（旧 F2 注释把方向搞反了，已废弃）。
async function queryConfidence(topic: string): Promise<any> {
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 1000);

    const response = await fetch(
      `${CA_API}/api/kg/confidence/${encodeURIComponent(topic)}`,
      { headers: COMMON_HEADERS, signal: controller.signal }
    );

    clearTimeout(timeout);
    if (!response.ok) {
      // F3: 失败可观测 —— 不再静默吞掉
      console.error(`[knowledge-gate] /api/kg/confidence HTTP ${response.status}`);
      return null;
    }
    return await response.json();
  } catch (err: any) {
    console.error(`[knowledge-gate] /api/kg/confidence failed: ${err?.message}`);
    return null;
  }
}

// C3D-R2 (v0.3.6): 同方向已结案发现查询。
// 重定向后的 C3-D：给定 topic → 返回同方向「已结案发现」→ 供 R1D3 消费提示。
// 作用：**扩大消费面**（让已探出的成果真正被用），不再收窄探索面。
async function queryRelatedDiscoveries(topic: string): Promise<any[]> {
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 1000);

    const response = await fetch(
      `${CA_API}/api/kg/related_discoveries/${encodeURIComponent(topic)}?k=3`,
      { headers: COMMON_HEADERS, signal: controller.signal }
    );

    clearTimeout(timeout);
    if (!response.ok) {
      console.error(`[knowledge-gate] related_discoveries HTTP ${response.status}`);
      return [];
    }
    const data = await response.json();
    return Array.isArray(data?.discoveries) ? data.discoveries : [];
  } catch (err: any) {
    console.error(`[knowledge-gate] related_discoveries failed: ${err?.message}`);
    return [];
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

    const confData = await queryConfidence(topic);
    // C3D-R2 (v0.3.6): 并行拉取同方向已结案发现（消费提示）。
    const discoveries = await queryRelatedDiscoveries(topic);

    const contextParts: string[] = [];

    // C1-C-3 (v0.3.6): 以 coverage 四态为主轴。
    // 四态映射（结论优先，按需展开）：
    //   known   → 直接引用 KG 作答
    //   partial → 初答 + 标注不确定性/缺口
    //   unknown → 先搜索再回答；CA 异步探索补全（不得静默）
    //   void    → 声明"系统层面无依据"
    const r = confData?.result ?? {};
    const coverage: string | undefined = r.coverage;
    const confidence: number =
      typeof r.confidence === 'number' ? r.confidence : 0;
    const reason: string = r.coverage_reason || 'unknown';
    const sourceCount: number = r.source_count ?? 0;
    const matched = r.matched_topic ? `（匹配到：${r.matched_topic}）` : '';
    const confPct = (confidence * 100).toFixed(0);
    const FOUR_STATE = ['known', 'partial', 'unknown', 'void'];

    if (coverage && FOUR_STATE.includes(coverage)) {
      // —— 四态主判定 ——
      if (coverage === 'known') {
        contextParts.push(
          `[KG Context — 已知${matched} ${confPct}%]\n` +
          `KG 有该主题的完整知识（来源 ${sourceCount} 条），直接引用作答并注明来源；无需强制搜索。`
        );
      } else if (coverage === 'partial') {
        contextParts.push(
          `[KG Context — 部分已知${matched} ${confPct}%]\n` +
          `KG 有部分知识：先给基于 KG 的初答，再搜索补充缺口。缺口原因：${reason}`
        );
      } else if (coverage === 'unknown') {
        contextParts.push(
          `[KG Context — 未知${matched}]\n` +
          `KG 无此主题：**先搜索**获取外部知识；若搜索无果，用 LLM 知识作答，` +
          `并注入 CA 探索以便后续补齐。**不得因置信度为 0 而静默。**`
        );
      } else {
        // void
        contextParts.push(
          `[KG Context — 无知识基础${matched}]\n` +
          `KG 无此主题且历史探索失败：**先搜索**；搜索无果则用 LLM 作答，` +
          `并**标注“系统对此主题无知识基础”**，勿凭 LLM 硬答，同时触发 CA 重新探索。`
        );
      }
    } else if (typeof r.confidence === 'number') {
      // —— 数值兜底（旧服务端 / 无 coverage 字段，零回归）——
      if (confidence >= 0.85) {
        contextParts.push(
          `[KG Context — 置信度高 ${confPct}%]\n` +
          `KG 有完整知识。`
        );
      } else if (confidence >= 0.6) {
        contextParts.push(
          `[KG Context — 置信度中 ${confPct}%]\n` +
          `KG 有部分知识，建议搜索补充。`
        );
      } else if (confidence > 0) {
        contextParts.push(
          `[KG Context — 置信度低 ${confPct}%]\n` +
          `KG 知识有限。`
        );
      }
    } else {
      console.warn('[knowledge-gate] confidence 响应缺少 coverage 与 confidence 字段，跳过注入');
    }

    if (contextParts.length > 0) {
      context.additionalContext = (context.additionalContext || '') + '\n\n' + contextParts.join('\n\n');
    }

    // C3D-R2 (v0.3.6): 同方向已结案发现 —— 消费提示。
    // 目的：让 CA 探出的成果真正被用（**扩大消费面**）。
    // 与四态注入分开：这是"可参考的相关知识"，不是"该 topic 的状态"。
    if (discoveries.length > 0) {
      const lines = discoveries
        .map((d: any) => `- ${d.topic}（相似度 ${(d.similarity * 100).toFixed(0)}%）`)
        .join('\n');
      const relatedBlock =
        `[相关发现 — 系统探过的同方向知识]\n` +
        `以下是与当前话题同方向的、系统已探索并有质量的内容，可按需引用：\n${lines}`;
      context.additionalContext =
        (context.additionalContext || '') + '\n\n' + relatedBlock;
    }
  } catch (err: any) {
    // 绝不 throw — 但留日志（F3）
    console.error(`[knowledge-gate] Failed: ${err.message}`);
  }
};
