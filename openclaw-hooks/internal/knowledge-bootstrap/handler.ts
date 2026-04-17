const CA_API = process.env.CA_API_URL || 'http://localhost:4848';

const handler = async (event: any) => {
  // 只处理 researcher agent
  if (event.context?.agentId !== 'researcher') return;
  
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 1500);
    
    const response = await fetch(
      `${CA_API}/api/kg/overview`,
      {
        headers: {
          "Content-Type": "application/json",
          "X-OpenClaw-Agent-Id": "r1d3",
          "X-OpenClaw-Hook-Name": "knowledge-bootstrap",
          "X-OpenClaw-Hook-Event": "agent:bootstrap",
          "X-OpenClaw-Hook-Type": "internal"
        },
        signal: controller.signal
      }
    );
    clearTimeout(timeout);
    
    if (response.ok) {
      const result = await response.json();
      const nodes = result.nodes || [];
      
      if (nodes.length > 0) {
        const summary = nodes
          .slice(0, 5)
          .map((n: any, i: number) =>
            `${i + 1}. **${n.id}** (quality: ${n.quality || 'N/A'})`
          )
          .join('\n');
        
        event.messages.push(
          `[CA Knowledge Summary]\n` +
          `你最近探索的话题：\n\n${summary}`
        );
      }
    }
  } catch (err: any) {
    console.error(`[knowledge-bootstrap] Failed: ${err.message}`);
  }
};

export default handler;