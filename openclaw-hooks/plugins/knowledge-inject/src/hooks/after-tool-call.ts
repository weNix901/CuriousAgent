const CA_API = process.env.CA_API_URL || 'http://localhost:4848';

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
  if (toolName !== 'web_search') return;
  
  if (!result || !result.output) return;
  
  const summary = extractSummary(result);
  const urls = extractUrls(result);
  
  if (urls.length === 0) {
    console.log('[knowledge-inject] No URLs found, skipping');
    return;
  }
  
  const topic = extractTopic(context);
  if (!topic) return;
  
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 1000);
    
    await fetch(`${CA_API}/api/knowledge/record`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ topic, content: summary, sources: urls }),
      signal: controller.signal
    });
    
    clearTimeout(timeout);
    console.log(`[knowledge-inject] Injected "${topic}" with ${urls.length} URLs`);
  } catch (err: any) {
    console.error(`[knowledge-inject] Failed: ${err.message}`);
  }
};