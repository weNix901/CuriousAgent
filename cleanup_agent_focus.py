#!/usr/bin/env python3
"""cleanup_agent_focus.py — 保留 Agent 相关 items，移除其他"""
import json, shutil, sys

STATE_FILE = "knowledge/state.json"
BACKUP_FILE = "knowledge/state.json.bak_agent_focus"

KEEP_ORIGINS = {
    # Agent harness
    'Agent harness OpenAI context engineering',
    'Middleware lifecycle hooks agent harness',
    'Anthropic Claude Agent SDK harness architecture',
    'Harness extension points for customization',
    'Agent Harness reproducibility configuration',
    # Agent 自由化
    'Agent Skills',
    'Few-shot calibration',
    'create_agent',
    # Agent 记忆
    'Context management',
    'Context compaction',
    'Context compression techniques for OpenAI agents',
    'State persistence',
    'Structured context handoff',
    'Structured artifact context handoff',
    'Isolated context window',
    'Pluggable virtual filesystem backends',
    'Git version control for agent state management',
    # Agent 控制
    'AgentMiddleware',
    'PIIMiddleware',
    'LLMToolSelectorMiddleware',
    'SummarizationMiddleware',
    'Middleware hook ordering and priority resolution',
    '[Post-invocation response interception hooks]',
    'Post-invocation result processing middleware hooks',
    'Pre-execution request interception middleware hooks',
    'Request/response interception handling',
    # Agent 行为模式
    'Self-correcting feedback loops',
    'Self-corrective context refinement for OpenAI agent reasoning',
    'Sub-agent delegation',
    'Sub-agent delegation multi-agent orchestration',
    'Sub-agent task decomposition granularity control',
    'Result aggregation from multiple delegated sub-agents',
    'Incremental result aggregation from multiple sub-agents',
    'Result aggregation for heterogeneous agent outputs',
    'Sub-agent execution result aggregation',
    'Initializer agent + Coding agent two-part architecture',
    'Hierarchical separation of concerns pattern',
    'Magentic orchestration',
    'Task decomposition',
    'deep reasearch',
    'A2A agentic protocol',
    'OpenAI /responses/compact endpoint',
    # Agent 通信/工具
    'Agent Client Protocol',
    'Agent Registry',
    'Claude Agent SDK',
    'MCP SDKs',
    'Model Context Protocol specification',
    'Model Context Protocol',
    # ICM / 好奇心
    'ICM computation overhead optimization for edge-deployed autonomous agents',
    'ICM computational overhead optimization for edge agents',
    'Intrinsic Curiosity Module (ICM)',
    'Intrinsic Curiosity Module',
    'ICM based exploration in partially observable environments',
    'ICM curiosity mechanism autonomous agent 2025',
    # JSON 格式跟踪
    'JSON formatted feature tracking file',
}

def main(dry_run=True):
    with open(STATE_FILE, 'r') as f:
        state = json.load(f)
    q = state['curiosity_queue']
    original = len(q)

    kept = [x for x in q if x.get('original_topic','') in KEEP_ORIGINS or x.get('original_topic','') == '']
    removed = [x for x in q if x.get('original_topic','') not in KEEP_ORIGINS and x.get('original_topic','') != '']

    print(f"原始队列: {original}")
    print(f"保留: {len(kept)} (Agent 相关)")
    print(f"移除: {len(removed)} (非 Agent 相关)")

    if dry_run:
        print("\n🟡 DRY RUN — 加 --no-dry-run 实际执行")
        return

    state['curiosity_queue'] = kept
    shutil.copy(STATE_FILE, BACKUP_FILE)
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    print(f"\n备份: {BACKUP_FILE}")
    print(f"✅ 保存: {original} → {len(kept)}")

if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--dry-run', action='store_true')
    p.add_argument('--no-dry-run', dest='dry_run', action='store_false')
    p.set_defaults(dry_run=True)
    main(p.parse_args().dry_run)
