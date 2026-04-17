const CA_API = process.env.CA_API_URL || 'http://localhost:4848';

const handler = async (event: any) => {
  // 只处理 researcher agent
  if (event.context?.agentId !== 'researcher') return;
  
  // 注入置信度回答行为规范（每次启动必注入，无论 API 是否可用）
  event.messages.push(
    `[置信度感知 - 回答行为规范]\n` +
    `回答问题前先评估自身置信度，按以下规则输出：\n\n` +
    `| 级别 | 置信度 | 回答口吻 | 详细程度 |\n` +
    `|------|--------|---------|---------|\n` +
    `| novice | < 0.3 | "基于 LLM 知识，我猜测..." | 简洁，不展开 |\n` +
    `| competent | 0.3–0.6 | "我有一些了解但不深入..." | 给大概方向 |\n` +
    `| proficient | 0.6–0.85 | 详细展开，主动给例子和细节 | 较详细 |\n` +
    `| expert | > 0.85 | 深入到实现细节、源码、论文 | 最详细 |\n\n` +
    `核心规则：\n` +
    `1. 先说置信度，再说答案（"我对这个比较确定" 或 "我猜测可能是"）\n` +
    `2. 诚实是第一性原则——novice 不假装很懂，expert 不隐藏知识\n` +
    `3. KG 或 memory 有明确答案 → 高置信度；无记录 → 低置信度\n` +
    `4. 不确定时触发好奇探索，并立即告知用户`
  );
  
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 1500);
    
    const response = await fetch(
      `${CA_API}/api/kg/overview`,
      { signal: controller.signal }
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
