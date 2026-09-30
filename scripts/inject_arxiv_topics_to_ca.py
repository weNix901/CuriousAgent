#!/usr/bin/env python3
"""
ArXiv AI Research Digest → CA 好奇心注入
从 duanyytop/agents-radar 获取每日 ArXiv AI Research Digest，
提取「Agents & Reasoning」板块论文，注入 CA 好奇心队列。
"""

import json
import re
import subprocess
import sys
import socket
from html import unescape as html_unescape

# 全局超时保护（秒）- 使用 socket 超时而非 signal
GLOBAL_TIMEOUT = 90
socket.setdefault_timeout(GLOBAL_TIMEOUT)


def fetch_arxiv_digest_issues():
    """获取 ArXiv AI Research Digest 最新 issue 编号"""
    url = "https://github.com/duanyytop/agents-radar/issues?q=is%3Aissue+ArXiv+AI+Research+Digest"
    
    html_content = fetch_with_curl(url, timeout=15)
    if not html_content:
        html_content = fetch_with_urllib(url, timeout=10)
    
    if not html_content:
        print("❌ curl 和 urllib 均无法获取 issue 列表")
        return None
    
    issue_matches = re.findall(r'/duanyytop/agents-radar/issues/(\d+)', html_content)
    if not issue_matches:
        print("❌ 未找到 ArXiv AI Research Digest issue")
        return None
    
    return issue_matches[0]


def fetch_with_curl(url, timeout=20):
    """使用 curl 获取 URL，带超时和连接超时"""
    try:
        return subprocess.check_output(
            ['curl', '-s', '--max-time', str(timeout), '-L',
             '--connect-timeout', '8',
             '-A', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
             url],
            stderr=subprocess.DEVNULL, timeout=timeout + 5
        ).decode('utf-8', errors='ignore')
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, OSError) as e:
        return None

def fetch_with_urllib(url, timeout=15):
    """urllib fallback 获取 URL"""
    try:
        import urllib.request
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Accept': 'text/html',
        })
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read(500000).decode('utf-8', errors='ignore')
    except Exception:
        return None

def fetch_issue_content(issue_num):
    """获取指定 issue 的内容（curl 为主，urllib fallback）"""
    issue_url = f"https://github.com/duanyytop/agents-radar/issues/{issue_num}"
    
    # curl 方案
    result = fetch_with_curl(issue_url, timeout=20)
    if result and len(result) > 1000:
        return result
    
    # urllib fallback
    result = fetch_with_urllib(issue_url)
    if result and len(result) > 1000:
        return result
    
    print(f"❌ 获取 issue 内容失败")
    return None


def extract_agent_papers(text):
    """从页面文本中提取 Agents & Reasoning 板块的论文标题
    
    返回论文标题列表，每个标题单独作为字符串
    """
    # 移除脚本和样式
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
    text = re.sub(r'<br\s*/?>', '\n', text)
    text = re.sub(r'</p>', '\n', text)
    text = re.sub(r'</div>', '\n', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = html_unescape(text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    lines = text.split('\n')
    
    # 找到 Agents & Reasoning 板块
    agent_lines = []
    in_agent_section = False
    stop_keywords = ['Navigation Menu', 'Saved searches', 'Sign in', 'Footer navigation',
                     'Previous', 'Next', ' Issues', 'Pull requests', '#### 7.']
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if any(sw in line for sw in stop_keywords):
            break
        # 检测板块开始
        if 'Agents' in line and 'Reasoning' in line:
            in_agent_section = True
            continue
        if in_agent_section:
            agent_lines.append(line)
            if len(agent_lines) > 200:
                break
    
    if not agent_lines:
        return []
    
    # 提取论文标题
    titles = []
    
    for line in agent_lines:
        line = line.strip()
        if not line:
            continue
        
        # 跳过元数据行
        if any(k in line for k in ['Link:', 'Authors:', 'http', 'arxiv.org', '####', '###']):
            continue
        
        # 论文标题特征：
        # 1. 长度 20-250 字符
        # 2. 不以小写字母开头（避免句子片段）
        # 3. 包含学术词汇
        # 4. 不是纯大写（避免标题栏）
        if 20 <= len(line) <= 250 and not line[0].islower():
            # 学术关键词检查
            academic_keywords = [
                'agent', 'agents', 'reasoning', 'planning', 'llm', 'model', 
                'learning', 'network', 'architecture', 'framework', 'system',
                'language', 'knowledge', 'intelligence', 'neural', 'deep',
                'reinforcement', 'supervised', 'unsupervised', 'transformer',
                'attention', 'embedding', 'generation', 'understanding',
                'multimodal', 'vision', 'robotics', 'autonomous', 'tool',
                'chain', 'prompt', 'fine-tuning', 'distillation', 'bias',
                'fairness', 'robustness', 'generalization', 'efficient',
                'scalable', 'distributed', 'federated', 'online', 'offline'
            ]
            
            has_academic_kw = any(kw in line.lower() for kw in academic_keywords)
            
            # 排除纯数字、纯符号
            has_letters = any(c.isalpha() for c in line)
            
            if has_academic_kw and has_letters:
                # 清理标题
                clean = re.sub(r'\s+', ' ', line).strip()
                # 去除 markdown 标记
                clean = re.sub(r'^[*\-#>\s]+', '', clean)
                if len(clean) >= 20:
                    titles.append(clean)
    
    # 去重并保持顺序
    seen = set()
    unique_titles = []
    for t in titles:
        if t not in seen:
            seen.add(t)
            unique_titles.append(t)
    
    return unique_titles[:15]  # 最多15篇


def inject_to_ca(topic: str, ca_api_url: str, depth: float = 7.0, parent: str = None) -> bool:
    """通过 CA API 注入好奇心 topic"""
    try:
        import urllib.request
        
        payload = {
            "topic": topic,
            "alpha": 0.5,
            "mode": "fusion",
            "depth": depth
        }
        if parent:
            payload["parent"] = parent
        
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(
            f"{ca_api_url}/api/curious/inject",
            data=data,
            headers={
                'Content-Type': 'application/json',
                'User-Agent': 'Mozilla/5.0'
            },
            method='POST'
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            result = json.loads(resp.read().decode('utf-8'))
            return result.get('status') == 'success'
    except Exception as e:
        print(f"   ⚠️ 注入失败 [{topic[:40]}]: {str(e)[:60]}")
        return False


def main():
    print("📚 ArXiv AI Research Digest → CA 好奇心注入")
    print(f"   时间: {subprocess.check_output(['date', '+%Y-%m-%d %H:%M']).decode().strip()}")
    print()
    
    # 1. 获取最新 ArXiv Digest issue
    print("🔍 获取 ArXiv AI Research Digest...")
    latest_issue = fetch_arxiv_digest_issues()
    if not latest_issue:
        print("❌ 无法获取 ArXiv Digest，尝试备用方案...")
        # fallback: 直接尝试几个已知的高编号
        for try_issue in ['1000', '999', '998', '995', '990']:
            issue_html = fetch_issue_content(try_issue)
            if issue_html and 'ArXiv' in issue_html:
                latest_issue = try_issue
                print(f"   ✓ 使用 issue #{latest_issue}")
                break
        if not latest_issue:
            print("❌ 所有方案均失败")
            sys.exit(1)
    
    print(f"   最新 issue: #{latest_issue}")
    
    # 2. 获取 issue 内容
    print(f"📥 获取 issue 内容...")
    issue_html = fetch_issue_content(latest_issue)
    if not issue_html:
        print("❌ 无法获取 issue 内容")
        sys.exit(1)
    
    # 3. 提取论文
    print("📄 提取 Agents & Reasoning 论文...")
    papers = extract_agent_papers(issue_html)
    if not papers:
        print("❌ 未找到论文，尝试全文关键词匹配...")
        # 最后 fallback：提取含关键词的完整行
        text_clean = re.sub(r'<[^>]+>', '', issue_html)
        text_clean = html_unescape(text_clean)
        all_lines = text_clean.split('\n')
        for line in all_lines:
            line = line.strip()
            if len(line) > 30 and len(line) < 200 and not line.startswith('http'):
                if any(kw in line.lower() for kw in ['agent', 'reasoning', 'planning', 'llm', 'multi']):
                    papers.append({'title': line})
        papers = papers[:8]
    
    print(f"   找到 {len(papers)} 篇论文")
    for i, title in enumerate(papers, 1):
        print(f"   {i}. {title[:80]}")
    print()
    
    # 4. CA API 配置（尝试多个可能地址）
    import urllib.request
    ca_urls_to_try = [
        "http://10.1.0.13:4848",
        "http://localhost:4848",
        "http://host.docker.internal:4848",
    ]
    ca_api_url = None
    for url in ca_urls_to_try:
        try:
            req = urllib.request.Request(
                f"{url}/api/quota/status",
                headers={'User-Agent': 'Mozilla/5.0'}
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                status = json.loads(resp.read().decode('utf-8'))
                ca_api_url = url
                print(f"✅ CA 状态: {status.get('status', 'unknown')} (via {url})")
                break
        except Exception as e:
            print(f"   ⚠️ {url} 不可用: {str(e)[:40]}")
    
    if not ca_api_url:
        print("❌ 所有 CA API 地址均不可用")
        print("   topics 记录到日志供后续处理")
        for title in papers:
            print(f"   • {title[:80]}")
        # 不 sys.exit(0)，继续尝试注入（也许实际上可以）
    
    # 5. 注入每篇论文到 CA
    print()
    print("🚀 开始注入 CA 好奇心队列...")
    parent_topic = f"ArXiv AI Research #{latest_issue} - Agents & Reasoning"
    
    injected = 0
    failed = 0
    for title in papers:
        if not title:
            continue
        
        # 注入完整论文标题作为 topic
        # 添加前缀明确来源
        topic = f"[ArXiv] {title}"
        
        ok = inject_to_ca(topic, ca_api_url, depth=7.0, parent=parent_topic)
        if ok:
            print(f"   ✅ {title[:70]}")
            injected += 1
        else:
            print(f"   ❌ {title[:70]}")
            failed += 1
    
    print()
    print(f"📊 注入完成: {injected} 成功, {failed} 失败")
    
    if injected > 0:
        print(f"   CA 好奇心队列已加入 {parent_topic}")
        print(f"   共 {len(papers)} 篇论文，等待 CA 探索")


if __name__ == "__main__":
    main()
