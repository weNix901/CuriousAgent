"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.afterToolCallHook = void 0;
const CA_API = process.env.CA_API_URL || 'http://localhost:4848';
function extractSummary(result) {
    try {
        const parsed = typeof result.output === 'string' ? JSON.parse(result.output) : result.output;
        if (parsed.answer)
            return parsed.answer;
        const snippets = (parsed.results || []).slice(0, 3).map((r) => r.snippet);
        return snippets.join('\n\n');
    }
    catch {
        return String(result.output).slice(0, 1000);
    }
}
function extractUrls(result) {
    try {
        const parsed = typeof result.output === 'string' ? JSON.parse(result.output) : result.output;
        return (parsed.results || [])
            .map((r) => r.url)
            .filter((url) => url && url.startsWith('http'))
            .slice(0, 10);
    }
    catch {
        return [];
    }
}
function extractTopic(context) {
    const messages = context.messages || [];
    for (let i = messages.length - 1; i >= 0; i--) {
        if (messages[i].role === 'user' && messages[i].content) {
            return messages[i].content.trim().slice(0, 80);
        }
    }
    return '';
}
const afterToolCallHook = async ({ toolName, result, context }) => {
    // 只处理 researcher agent
    if (context?.agentId !== 'researcher')
        return;
    if (!/search$/i.test(toolName))
        return;
    if (!result || !result.output)
        return;
    const summary = extractSummary(result);
    const urls = extractUrls(result);
    if (urls.length === 0) {
        console.log('[knowledge-inject] No URLs found, skipping');
        return;
    }
    const topic = extractTopic(context);
    if (!topic)
        return;
    try {
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 1000);
        await fetch(`${CA_API}/api/knowledge/record`, {
            method: 'POST',
            headers: {
                "Content-Type": "application/json",
                "X-OpenClaw-Agent-Id": "r1d3",
                "X-OpenClaw-Hook-Name": "knowledge-inject",
                "X-OpenClaw-Hook-Event": "after_tool_call",
                "X-OpenClaw-Hook-Type": "plugin_sdk"
            },
            body: JSON.stringify({ topic, content: summary, sources: urls }),
            signal: controller.signal
        });
        clearTimeout(timeout);
        console.log(`[knowledge-inject] Injected "${topic}" with ${urls.length} URLs`);
    }
    catch (err) {
        console.error(`[knowledge-inject] Failed: ${err.message}`);
    }
};
exports.afterToolCallHook = afterToolCallHook;
