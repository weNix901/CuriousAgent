const CA_API = process.env.CA_API_URL || 'http://localhost:4848';

const CONFIG = {
  MIN_CONTENT_LENGTH: 50,
  MAX_REACT_RATIO: 0.5,
};

function filterReActContent(text: string): string {
  text = text.replace(/Thought:[\s\S]*?(?=Action:|Observation:|$)/gi, '');
  text = text.replace(/Action:[\s\S]*?(?=Observation:|Thought:|$)/gi, '');
  text = text.replace(/Observation:[\s\S]*?(?=Thought:|Action:|$)/gi, '');
  text = text.replace(/<\|FunctionCallBegin\|>[\s\S]*?<\|FunctionCallEnd\|>/gi, '');
  text = text.replace(/\n{3,}/g, '\n\n').trim();
  return text;
}

function extractSummary(result: any): string {
  try {
    const parsed = typeof result.output === 'string' ? JSON.parse(result.output) : result.output;
    if (parsed.answer) return parsed.answer;
    const snippets = (parsed.results || []).slice(0, 3).map((r: any) => r.snippet);
    return snippets.join('\n\n');
  } catch {
    return String(result.output).slice(0, 1000);
  }
}

function extractUrls(result: any): string[] {
  try {
    const parsed = typeof result.output === 'string' ? JSON.parse(result.output) : result.output;
    return (parsed.results || [])
      .map((r: any) => r.url)
      .filter((url: string) => url && url.startsWith('http'))
      .slice(0, 10);
  } catch {
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

export const afterToolCallHook = async ({ toolName, result, context }: any) => {
  if (context?.agentId !== 'researcher') return;
  if (!/search$/i.test(toolName)) return;
  
  if (!result || !result.output) return;
  
  const summary = extractSummary(result);
  const urls = extractUrls(result);
  
  if (urls.length === 0) {
    console.log('[knowledge-inject] No URLs found, skipping');
    return;
  }
  
  const topic = extractTopic(context);
  if (!topic) return;
  
  if (summary.length < CONFIG.MIN_CONTENT_LENGTH) {
    console.log('[knowledge-inject] Content too short, skipping');
    return;
  }
  
  const reactMarkers = ['Thought:', 'Action:', 'Observation:'];
  const reactCount = reactMarkers.filter(m => summary.includes(m)).length;
  if (reactCount / reactMarkers.length > CONFIG.MAX_REACT_RATIO) {
    console.log('[knowledge-inject] Content is mostly ReAct, skipping');
    return;
  }
  
  const cleanedSummary = filterReActContent(summary);
  
  if (cleanedSummary.length < CONFIG.MIN_CONTENT_LENGTH) {
    console.log('[knowledge-inject] Content too short after filtering, skipping');
    return;
  }
  
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 1000);
    
    const response = await fetch(`${CA_API}/api/knowledge/record`, {
      method: 'POST',
      headers: {
        "Content-Type": "application/json",
        "X-OpenClaw-Agent-Id": "r1d3",
        "X-OpenClaw-Hook-Name": "knowledge-inject",
        "X-OpenClaw-Hook-Event": "after_tool_call",
        "X-OpenClaw-Hook-Type": "plugin_sdk"
      },
      body: JSON.stringify({ topic, content: cleanedSummary, sources: urls }),
      signal: controller.signal
    });
    
    clearTimeout(timeout);
    if (!response.ok) {
      console.error(`[knowledge-inject] HTTP ${response.status}`);
      return;
    }
    console.log(`[knowledge-inject] Injected "${topic}" with ${urls.length} URLs`);
  } catch (err: any) {
    console.error(`[knowledge-inject] Failed: ${err.message}`);
  }
};
