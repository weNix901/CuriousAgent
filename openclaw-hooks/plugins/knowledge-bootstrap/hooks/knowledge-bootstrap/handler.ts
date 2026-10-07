const CA_API = process.env.CA_API_URL || 'http://localhost:4848';

// [2026-10-07 v0.3.6] knowledge-bootstrap 404 修复（方案 A）
//
// 旧实现打 `GET /api/kg/overview` —— 该路由已于 09d6b37（2026-04-17）删除，
// 每次会话启动打 404 → 被 catch 吞掉 → 会话级知识注入长期静默失效。
//
// 新实现打 `GET /api/knowledge/session/startup` —— 端点已存在，CA 侧直接
// 返回拼好的 `injection_content`（KG 摘要 + 认知框架 + skill 规则 + 主题提取）。
// 语义最对位（会话启动摘要），且避免"恢复历史路由"。
//
// 变更要点：
//   1. 端点切换 overview → session/startup
//   2. 消费服务端已拼好的 injection_content（不再本地拼 sections，
//      避免与 CA 侧模板/配置重复实现——单一真源在 CA）
//   3. 修 timeout_ms 缺失：DEFAULT_CONFIG 已含该字段，此处保持默认 1500ms
//   4. config 仍从 CA 拉取（enabled / timeout_ms 生效）

const DEFAULT_CONFIG = {
  enabled: true,
  timeout_ms: 1500
};

const handler = async (event: any) => {
  if (event.context?.agentId !== 'researcher') return;

  // --- config（仅取 enabled / timeout_ms；组装逻辑在 CA 侧）---
  let config = DEFAULT_CONFIG;
  try {
    const configResp = await fetch(`${CA_API}/api/hooks/bootstrap/config`, {
      headers: { "Content-Type": "application/json" },
      signal: AbortSignal.timeout(500)
    });
    if (configResp.ok) {
      const configData = await configResp.json();
      if (configData.config) {
        config = {
          ...DEFAULT_CONFIG,
          ...configData.config,
          // 防 undefined：服务端未返回时回退默认，避免 setTimeout(..., undefined)
          timeout_ms: configData.config.timeout_ms ?? DEFAULT_CONFIG.timeout_ms
        };
      }
    }
  } catch (e: any) {
    console.log(`[knowledge-bootstrap] Config fetch failed, using defaults`);
  }

  if (!config.enabled) return;

  // --- 拉取会话启动注入内容 ---
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), config.timeout_ms);

    const response = await fetch(`${CA_API}/api/knowledge/session/startup`, {
      headers: {
        "Content-Type": "application/json",
        "X-OpenClaw-Agent-Id": "r1d3",
        "X-OpenClaw-Hook-Name": "knowledge-bootstrap",
        "X-OpenClaw-Hook-Event": "agent:bootstrap",
        "X-OpenClaw-Hook-Type": "internal"
      },
      signal: controller.signal
    });
    clearTimeout(timeout);

    if (!response.ok) {
      console.error(`[knowledge-bootstrap] startup endpoint returned ${response.status}`);
      return;
    }

    const result = await response.json();
    const injectionContent = result.injection_content;

    if (!injectionContent) {
      console.log(`[knowledge-bootstrap] empty injection_content, nothing to inject`);
      return;
    }

    const nodesUsed = result.metadata?.nodes_used?.length || 0;

    if (event.context?.bootstrapFiles && Array.isArray(event.context.bootstrapFiles)) {
      event.context.bootstrapFiles.push({
        filename: 'CA_Knowledge_Context.md',
        content: injectionContent
      });
      console.log(`[knowledge-bootstrap] Injected to bootstrapFiles: ${nodesUsed} nodes`);
    } else if (event.messages && typeof event.messages.push === 'function') {
      event.messages.push(injectionContent);
      console.log(`[knowledge-bootstrap] Injected to messages: ${nodesUsed} nodes`);
    } else {
      console.log(`[knowledge-bootstrap] no injection target (bootstrapFiles/messages) on event`);
    }
  } catch (err: any) {
    console.error(`[knowledge-bootstrap] startup fetch failed: ${err.message}`);
  }
};

export default handler;
