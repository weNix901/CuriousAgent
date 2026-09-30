#!/usr/bin/env python3
"""
CA Three-Agent Monitor
监控 ExploreDaemon、DreamDaemon、SleepPruner 运行状态
"""

import sys
import os
import json
import logging
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def check_ca_api():
    """Check if CA API is responsive."""
    try:
        import socket
        import ssl
        
        # Simple socket check first
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        result = sock.connect_ex(('localhost', 4848))
        sock.close()
        
        if result != 0:
            return False, f"Port 4848 not reachable (error {result})"
        
        # Try HTTP request
        import urllib.request
        req = urllib.request.Request(
            "http://localhost:4848/api/quota/status",
            headers={'User-Agent': 'CA-Monitor'}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            return True, data
    except Exception as e:
        return False, str(e)


def get_agent_status():
    """Get three agent status from logs."""
    try:
        from core.kg.repository_factory import get_kg_factory
        from core.tools.queue_tools import QueueStorage
        
        kg_factory = get_kg_factory()
        queue_storage = QueueStorage()
        queue_storage.initialize()
        
        # KG stats
        nodes = kg_factory.get_all_nodes_sync(limit=5000)
        total_nodes = len(nodes)
        
        from collections import Counter
        statuses = Counter(n.get('status') for n in nodes)
        
        # Queue stats
        pending_items = queue_storage.get_pending_items()
        # claimed items - try to get from db directly
        try:
            import sqlite3
            conn = sqlite3.connect('/root/dev/curious-agent/knowledge/queue.db')
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM queue WHERE status = 'claimed'")
            claimed_count = c.fetchone()[0]
            conn.close()
        except:
            claimed_count = 0
        
        return {
            'kg_total': total_nodes,
            'kg_pending': statuses.get('pending', 0),
            'kg_done': statuses.get('done', 0),
            'kg_no_content': statuses.get('no_content', 0),
            'queue_pending': len(pending_items),
            'queue_claimed': claimed_count,
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        return {'error': str(e)}


def get_recent_log_activity():
    """Check recent activity in agent logs."""
    log_file = "/root/dev/curious-agent/logs/agent.log"
    if not os.path.exists(log_file):
        return "No log file"
    
    try:
        # Get last 50 lines
        import subprocess
        result = subprocess.run(
            ['tail', '-50', log_file],
            capture_output=True, text=True, timeout=5
        )
        lines = result.stdout.strip().split('\n')
        
        # Extract agent status
        explore_alive = False
        dream_alive = False
        sleep_alive = False
        
        for line in reversed(lines):
            if 'ExploreDaemon: alive=True' in line:
                explore_alive = True
            if 'DreamDaemon: running=True' in line:
                dream_alive = True
            if 'SleepPruner: alive=True' in line:
                sleep_alive = True
        
        return {
            'explore_daemon': '✅' if explore_alive else '❌',
            'dream_daemon': '✅' if dream_alive else '❌',
            'sleep_pruner': '✅' if sleep_alive else '❌',
        }
    except Exception as e:
        return {'error': str(e)}


def generate_report():
    """Generate full monitoring report."""
    lines = []
    now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    
    lines.append(f"📊 CA 三 Agent 监控报告 | {now}")
    lines.append("=" * 50)
    
    # API status
    api_ok, api_data = check_ca_api()
    if api_ok:
        lines.append(f"✅ CA API: 正常")
        providers = api_data.get('providers', {})
        for name, data in providers.items():
            lines.append(f"   {name}: {data.get('remaining', 'N/A')}/{data.get('limit', 'N/A')} 剩余")
    else:
        lines.append(f"❌ CA API: 异常 - {api_data}")
    
    lines.append("")
    
    # Agent process status
    log_status = get_recent_log_activity()
    if isinstance(log_status, dict) and 'error' not in log_status:
        lines.append("🤖 Agent 进程状态（最近日志）：")
        lines.append(f"   ExploreDaemon: {log_status.get('explore_daemon', '❓')}")
        lines.append(f"   DreamDaemon:   {log_status.get('dream_daemon', '❓')}")
        lines.append(f"   SleepPruner:   {log_status.get('sleep_pruner', '❓')}")
    else:
        lines.append(f"⚠️ 无法获取 Agent 状态: {log_status}")
    
    lines.append("")
    
    # KG & Queue stats
    stats = get_agent_status()
    if 'error' not in stats:
        lines.append("📈 KG 状态：")
        lines.append(f"   总节点: {stats['kg_total']}")
        lines.append(f"   Pending: {stats['kg_pending']} | Done: {stats['kg_done']} | NoContent: {stats['kg_no_content']}")
        lines.append("")
        lines.append("📋 Queue 状态：")
        lines.append(f"   Pending: {stats['queue_pending']} | Claimed: {stats['queue_claimed']}")
    else:
        lines.append(f"⚠️ 无法获取 KG/Queue 状态: {stats['error']}")
    
    lines.append("")
    
    # Health assessment
    issues = []
    if not api_ok:
        issues.append("CA API 不可访问")
    if isinstance(log_status, dict):
        if log_status.get('explore_daemon') == '❌':
            issues.append("ExploreDaemon 未运行")
        if log_status.get('dream_daemon') == '❌':
            issues.append("DreamDaemon 未运行")
        if log_status.get('sleep_pruner') == '❌':
            issues.append("SleepPruner 未运行")
    
    if stats.get('queue_pending', 0) > 100:
        issues.append(f"Queue 积压严重 ({stats['queue_pending']} pending)")
    if stats.get('kg_pending', 0) > 50:
        issues.append(f"KG pending 节点过多 ({stats['kg_pending']})")
    
    if issues:
        lines.append("⚠️ 发现的问题：")
        for issue in issues:
            lines.append(f"   - {issue}")
    else:
        lines.append("✅ 所有系统正常运行")
    
    lines.append("=" * 50)
    
    return "\n".join(lines)


def main():
    report = generate_report()
    print(report)
    
    # Also save to file for cron to pick up
    report_file = "/root/dev/curious-agent/logs/ca_monitor_latest.txt"
    try:
        with open(report_file, 'w') as f:
            f.write(report)
    except Exception as e:
        print(f"\n⚠️ 无法保存报告: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
