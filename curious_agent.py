#!/usr/bin/env python3
"""
Curious Agent MVP - 好奇 Agent
入口 + 调度器

用法:
  python3 curious_agent.py              # 运行一轮探索
  python3 curious_agent.py --daemon    # 守护进程模式（每30分钟探索一次）
  python3 curious_agent.py --status     # 查看当前状态
  python3 curious_agent.py --inject "topic"  # 注入新好奇心
"""
import argparse
import os
import sys
import time
from datetime import datetime, timezone

# Add core to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core import knowledge_graph as kg
from core.curiosity_engine import CuriosityEngine
from core.explorer import Explorer


VALID_DEPTHS = {"shallow", "medium", "deep"}


def run_one_cycle(depth: str = "medium") -> dict:
    if depth not in VALID_DEPTHS:
        raise ValueError(f"Invalid depth '{depth}'. Must be one of: {', '.join(sorted(VALID_DEPTHS))}")
    engine = CuriosityEngine()
    explorer = Explorer(exploration_depth=depth)
    
    # 1. 生成初始好奇心（如需要）
    engine.generate_initial_curiosities()
    
    # 2. 重新评分
    engine.rescore_all()
    
    # 3. 选择下一个
    next_curiosity = engine.select_next()
    if not next_curiosity:
        return {"status": "idle", "message": "没有待探索的好奇心"}
    
    # 4. 执行探索
    result = explorer.explore(next_curiosity)
    
    # 5. Auto-queue new topics from findings (only for medium/deep)
    auto_queued = 0
    if depth in ("medium", "deep"):
        findings = result.get("findings", "")
        keywords = engine._extract_keywords(findings)
        if keywords:
            auto_queued = engine.auto_queue_topics(keywords, parent_topic=next_curiosity["topic"])
    
    return {
        "status": "success",
        "result": result,
        "formatted": explorer.format_for_user(result),
        "auto_queued": auto_queued
    }


def print_status():
    """打印当前状态"""
    state = kg.get_state()
    summary = kg.get_knowledge_summary()
    
    print("=" * 50)
    print("👁️  Curious Agent MVP - 状态面板")
    print("=" * 50)
    print(f"🕒 最后更新: {state.get('last_update', '未知')}")
    print(f"📚 知识节点: {summary['total_topics']} 个")
    print(f"   - 已知: {summary['known_count']}")
    print(f"   - 未知: {summary['total_topics'] - summary['known_count']}")
    print(f"❓ 待探索好奇心: {summary['pending_curiosities']} 项")
    print(f"🗺️  探索历史: {summary['recent_explorations']} 条")
    print()
    
    pending = [i for i in state["curiosity_queue"] if i["status"] == "pending"]
    if pending:
        print("🔥 Top 好奇心队列:")
        for i, item in enumerate(sorted(pending, key=lambda x: x["score"], reverse=True)[:5], 1):
            status_icon = "⏳" if item["status"] == "pending" else "🔄" if item["status"] == "investigating" else "✅"
            print(f"   {i}. [{item['score']:.1f}] {status_icon} {item['topic']}")
            print(f"      → {item['reason']}")
    
    recent = state.get("exploration_log", [])
    if recent:
        print()
        print("📋 最近探索:")
        for log in recent[-3:]:
            icon = "📬" if log["notified_user"] else "📭"
            print(f"   {icon} [{log['action']}] {log['topic']}")
            print(f"      {log['findings'][:80]}...")
    
    print("=" * 50)


def daemon_mode(interval_minutes: int = 30):
    """守护进程模式"""
    print(f"🚀 Curious Agent 进入守护进程模式 (每 {interval_minutes} 分钟探索一次)")
    print("   按 Ctrl+C 停止")
    print()
    
    cycle_count = 0
    while True:
        cycle_count += 1
        print(f"\n{'='*50}")
        print(f"🔄 探索循环 #{cycle_count} @ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*50}")
        
        outcome = run_one_cycle()
        
        if outcome["status"] == "idle":
            print(f"💤 {outcome['message']}")
        else:
            result = outcome["result"]
            print(f"✅ 完成: {result['topic']}")
            print(f"   方式: {result['action']}")
            print(f"   分数: {result['score']}")
            print(f"   通知用户: {'是' if result['notified'] else '否'}")
            
            if result["notified"]:
                print(f"\n📬 飞书通知已触发（见下方内容）:")
                print("-" * 40)
                print(outcome["formatted"][:300])
        
        time.sleep(interval_minutes * 60)


def resolve_alpha(args) -> float:
    """解析 alpha 值，优先级：--pure-curious > --alpha > --motivation > default"""
    if getattr(args, 'pure_curious', False):
        return 0.0
    if getattr(args, 'alpha', None) is not None and args.alpha != 0.5:
        return args.alpha
    if getattr(args, 'motivation', None) == 'human':
        return 0.7
    if getattr(args, 'motivation', None) == 'curious':
        return 0.3
    return 0.5


def inject_curiosity(topic: str, relevance: float = 7.0, depth: float = 6.0, reason: str = "", alpha: float = 0.5):
    """注入新的好奇心项，使用融合评分"""
    if not reason:
        reason = f"用户主动注入: {topic}"
    
    # Use fusion scoring
    engine = CuriosityEngine()
    score_result = engine.score_topic(topic, alpha=alpha)
    
    # Add to queue with fusion score
    kg.add_curiosity(topic, reason, score_result['final_score'], depth)
    
    print(f"✅ 已注入好奇心: {topic}")
    print(f"   融合评分: {score_result['final_score']:.2f} (α={alpha})")
    print(f"   - 人工评分: {score_result['human_score']:.2f}")
    print(f"   - 内在评分: {score_result['intrinsic_score']:.2f}")
    print(f"   原因: {reason}")


def main():
    parser = argparse.ArgumentParser(description="Curious Agent MVP")
    parser.add_argument("--daemon", action="store_true", help="守护进程模式")
    parser.add_argument("--interval", type=int, default=30, help="守护进程探索间隔(分钟)")
    parser.add_argument("--status", action="store_true", help="查看状态")
    parser.add_argument("--inject", type=str, help="注入新好奇心 topic")
    parser.add_argument("--score", type=float, default=7.0, help="注入时的 relevance 分数")
    parser.add_argument("--depth", type=float, default=6.0, help="注入时的 depth 分数")
    parser.add_argument("--reason", type=str, default="", help="注入原因")
    parser.add_argument("--run", action="store_true", help="运行一轮探索")
    parser.add_argument("--run-depth", type=str, default="medium", choices=["shallow", "medium", "deep"], help="运行时的探索深度")
    parser.add_argument("--alpha", type=float, default=0.5, help="人工信号权重 (0.0-1.0)，默认 0.5")
    parser.add_argument("--motivation", type=str, choices=["human", "curious"], help="预设 alpha: human=0.7, curious=0.3")
    parser.add_argument("--pure-curious", action="store_true", help="纯探索模式 (alpha=0.0)")
    
    args = parser.parse_args()
    
    alpha = resolve_alpha(args)
    
    if args.status:
        print_status()
    elif args.inject:
        inject_curiosity(args.inject, args.score, args.depth, args.reason, alpha=alpha)
    elif args.daemon:
        daemon_mode(args.interval)
    elif args.run:
        result = run_one_cycle(depth=args.run_depth)
        if result["status"] == "idle":
            print(f"💤 {result['message']}")
        else:
            print(result["formatted"])
    else:
        result = run_one_cycle(depth=args.run_depth)
        print_status()
        if result["status"] == "success":
            print("\n📋 本轮探索结果:")
            print(result["formatted"])


if __name__ == "__main__":
    main()
