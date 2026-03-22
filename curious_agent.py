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
from core.reasoning_compressor import ReasoningCompressor, CompressionLevel


VALID_DEPTHS = {"shallow", "medium", "deep"}


def run_one_cycle(depth: str = "medium") -> dict:
    if depth not in VALID_DEPTHS:
        raise ValueError(f"Invalid depth '{depth}'. Must be one of: {', '.join(sorted(VALID_DEPTHS))}")
    
    from core.meta_cognitive_monitor import MetaCognitiveMonitor
    from core.meta_cognitive_controller import MetaCognitiveController
    from core.event_bus import EventBus
    from core.llm_manager import LLMManager
    from core.config import get_config
    
    # Load config and initialize LLMManager
    config = get_config()
    llm_config = {
        "providers": {},
        "selection_strategy": "capability"
    }
    for p in config.llm_providers:
        llm_config["providers"][p.name] = {
            "api_url": p.api_url,
            "timeout": p.timeout,
            "enabled": p.enabled,
            "models": [
                {"model": m.model, "weight": m.weight, "capabilities": m.capabilities, "max_tokens": m.max_tokens}
                for m in p.models
            ]
        }
    
    engine = CuriosityEngine()
    
    engine.generate_initial_curiosities()
    engine.rescore_all()
    
    next_curiosity = engine.select_next()
    if not next_curiosity:
        return {"status": "idle", "message": "No pending curiosities"}
    
    topic = next_curiosity["topic"]
    
    llm_manager = LLMManager.get_instance(llm_config)
    monitor = MetaCognitiveMonitor(llm_client=llm_manager)
    controller = MetaCognitiveController(monitor)
    
    allowed, reason = controller.should_explore(topic)
    if not allowed:
        print(f"[MGV] Exploration blocked: {topic} — {reason}")
        kg.mark_topic_done(topic, reason)
        EventBus.emit("exploration.blocked", {"topic": topic, "reason": reason})
        return {"status": "blocked", "topic": topic, "reason": reason}
    
    explorer = Explorer(exploration_depth=depth)
    result = explorer.explore(next_curiosity)
    
    findings = {
        "summary": result.get("findings", ""),
        "sources": result.get("sources", []),
        "papers": result.get("papers", [])
    }
    
    quality = monitor.assess_exploration_quality(topic, findings)
    marginal = monitor.compute_marginal_return(topic, quality)
    exploration_count = monitor.get_explore_count(topic)
    
    # 应用认知跳跃压缩（基于当前 quality）
    compressor = ReasoningCompressor()
    compression = compressor.compress(
        topic=topic,
        quality=quality,
        marginal_return=marginal,
        exploration_count=exploration_count,
        depth=depth,
        layer_count=result.get("action", "").count("+") + 1,
        findings=result.get("findings", "")
    )
    compression_level = compression.level
    
    # 通知决策：quality >= 7.0 且 非 SILENT 压缩
    should_notify = (quality >= 7.0) and (compression.level != CompressionLevel.SILENT)
    notified = False
    formatted = ""
    
    if should_notify:
        formatted = compressor.format_output(result, compression)
        
        EventBus.emit("discovery.high_quality", {
            "topic": topic,
            "quality": quality,
            "formatted": formatted,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        EventBus.emit("notification.external", {
            "topic": topic,
            "quality": quality,
            "message": formatted
        })
        
        kg.update_last_exploration_notified(topic, True)
        notified = True
    elif compression.level == CompressionLevel.SILENT:
        # SILENT 级别：记录但不通知
        print(f"[ReasoningCompressor] SILENT 跳过: {topic} (Q={quality:.1f}, marginal={marginal:.2f})")
    else:
        # 质量不足（< 7.0）但非 SILENT：静默记录，不推送
        pass
    
    monitor.record_exploration(topic, quality, marginal, notified=notified)
    
    continue_allowed, continue_reason = controller.should_continue(topic)
    
    if continue_allowed:
        kg.add_curiosity(
            topic,
            reason=f"Marginal:{marginal:.2f}, Quality:{quality:.1f}",
            relevance=quality / 10.0,
            depth=quality / 10.0 * 5
        )
    else:
        kg.mark_topic_done(topic, continue_reason)
        EventBus.emit("exploration.completed", {
            "topic": topic,
            "reason": continue_reason,
            "final_quality": quality
        })
    
    auto_queued = 0
    if depth in ("medium", "deep"):
        keywords = engine._extract_keywords(findings["summary"])
        if keywords:
            auto_queued = engine.auto_queue_topics(keywords, parent_topic=topic)
    
    # 使用压缩后的 formatted（若 should_notify=False 则为空）
    final_formatted = formatted if should_notify else explorer.format_for_user(result)

    return {
        "status": "success",
        "topic": topic,
        "result": result,
        "formatted": final_formatted,
        "quality": quality,
        "marginal_return": marginal,
        "notified": notified,
        "continue": continue_allowed,
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
    
    engine = CuriosityEngine()
    score_result = engine.score_topic(topic, alpha=alpha)
    kg.add_curiosity(topic, reason, score_result['final_score'], depth)
    
    print(f"✅ 已注入好奇心: {topic}")
    print(f"   融合评分: {score_result['final_score']:.2f} (α={alpha})")
    print(f"   - 人工评分: {score_result['human_score']:.2f}")
    print(f"   - 内在评分: {score_result['intrinsic_score']:.2f}")
    print(f"   原因: {reason}")


def delete_curiosity(topic: str, force: bool = False):
    """删除队列条目"""
    success = kg.remove_curiosity(topic, force=force)
    if success:
        print(f"✅ 已删除: {topic}")
    else:
        print(f"❌ 删除失败: {topic} (可能不存在或状态不允许删除，使用 --force 强制删除)")


def list_pending():
    """列出待探索条目"""
    pending = kg.list_pending()
    if not pending:
        print("📭 没有待探索的条目")
        return
    
    print(f"📋 待探索条目 ({len(pending)} 项):")
    for i, item in enumerate(pending, 1):
        print(f"   {i}. [{item.get('score', 'N/A'):.1f}] {item['topic']}")


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
    parser.add_argument("--delete", type=str, help="删除指定话题")
    parser.add_argument("--force", action="store_true", help="强制删除（忽略状态）")
    parser.add_argument("--list-pending", action="store_true", help="列出待探索条目")
    
    args = parser.parse_args()
    
    alpha = resolve_alpha(args)
    
    if args.status:
        print_status()
    elif args.list_pending:
        list_pending()
    elif args.delete:
        delete_curiosity(args.delete, force=args.force)
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
