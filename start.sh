#!/bin/bash
#
# Curious Agent 启动脚本
# - 清理旧进程
# - 检查依赖服务
# - 启动所有服务
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[STARTUP]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
err() { echo -e "${RED}[ERR]${NC} $1"; }

# === 1. 清理旧进程 ===
log "检查旧进程..."

# 查找 curious_agent 和 curious_api 进程
OLD_AGENT_PIDS=$(ps aux | grep "curious_agent.py" | grep -v grep | awk '{print $2}' || true)
OLD_API_PIDS=$(ps aux | grep "curious_api.py" | grep -v grep | awk '{print $2}' || true)

if [ -n "$OLD_AGENT_PIDS" ]; then
    warn "发现旧 curious_agent 进程: $OLD_AGENT_PIDS"
    echo "$OLD_AGENT_PIDS" | xargs kill -9 2>/dev/null || true
    log "已杀掉 curious_agent"
fi

if [ -n "$OLD_API_PIDS" ]; then
    warn "发现旧 curious_api 进程: $OLD_API_PIDS"
    echo "$OLD_API_PIDS" | xargs kill -9 2>/dev/null || true
    log "已杀掉 curious_api"
fi

# 清理 PID 文件
[ -f /tmp/curious_agent_daemon.pid ] && rm -f /tmp/curious_agent_daemon.pid

sleep 1

# === 2. 检查依赖服务 ===
log "检查依赖服务..."

# Neo4j
if systemctl is-active --quiet neo4j 2>/dev/null; then
    log "Neo4j: 已运行"
else
    warn "Neo4j 未运行，尝试启动..."
    systemctl start neo4j 2>/dev/null && log "Neo4j 已启动" || err "Neo4j 启动失败"
fi

# 检查 Neo4j HTTP 端口
if curl -s --connect-timeout 3 http://localhost:7474/ > /dev/null 2>&1; then
    log "Neo4j HTTP (7474): 可用"
else
    err "Neo4j HTTP 不可用"
fi

if curl -s --connect-timeout 3 http://localhost:7687/ > /dev/null 2>&1; then
    log "Neo4j Bolt (7687): 可用"
else
    warn "Neo4j Bolt 端口未响应（可能正常）"
fi

# 确保日志目录存在
mkdir -p logs

# === 3. 加载环境变量 ===
if [ -f .env ]; then
    log "加载 .env"
    source .env
else
    err ".env 文件不存在"
    exit 1
fi

# === 4. 启动 curious_api ===
log "启动 curious_api..."
nohup python3 curious_api.py > logs/api.log 2>&1 &
API_PID=$!
echo $API_PID > /tmp/curious_api.pid
log "curious_api 启动 (PID: $API_PID)"

# 等待 API 就绪
sleep 3

# 检查 API 是否正常
if curl -s --connect-timeout 5 http://localhost:4848/api/quota/status > /dev/null 2>&1; then
    log "curious_api HTTP: 就绪"
else
    err "curious_api 启动异常"
    cat logs/api.log | tail -20
fi

# === 5. 启动 curious_agent (daemon mode) ===
log "启动 curious_agent..."
nohup python3 curious_agent.py --daemon --interval 30 > logs/agent.log 2>&1 &
AGENT_PID=$!
log "curious_agent 启动 (PID: $AGENT_PID)"

sleep 2

# === 6. 最终状态 ===
echo ""
log "=== 启动完成 ==="
echo ""
echo "进程状态:"
ps aux | grep -E "curious_agent|curious_api" | grep -v grep | awk '{print "  "$11" "$12" (PID:"$2")"}' || true
echo ""
echo "日志文件:"
echo "  - curious_api: logs/api.log"
echo "  - curious_agent: logs/agent.log"
echo ""
echo "API 端点: http://localhost:4848"
echo "Neo4j: bolt://localhost:7687"
echo ""
