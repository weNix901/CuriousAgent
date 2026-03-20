#!/bin/bash
# run_curious.sh - Curious Agent 一键启动脚本

PORT=${PORT:-4848}
APP_DIR="/root/dev/curious-agent"
LOG_FILE="$APP_DIR/logs/api.log"

echo "🚀 Curious Agent 启动脚本"
echo "=========================="

# 1. 检测占用端口的进程
echo "[1/5] 检测端口 $PORT ..."
if command -v fuser &> /dev/null; then
    fuser -k ${PORT}/tcp 2>/dev/null || true
    echo "   ✓ 已清理端口 $PORT"
fi

# 2. Kill 残留的 curious 进程
echo "[2/5] 清理残留进程 ..."
pkill -f "curious_api.py" 2>/dev/null && echo "   ✓ 已终止 curious_api.py"
pkill -f "curious_agent.py" 2>/dev/null && echo "   ✓ 已终止 curious_agent.py"

# 3. 等待端口释放
echo "[3/5] 等待端口释放 ..."
sleep 2

# 4. 启动服务
echo "[4/5] 启动 Curious Agent API ..."
cd "$APP_DIR"
nohup python3 curious_api.py > "$LOG_FILE" 2>&1 &
PID=$!
echo "   ✓ 服务 PID: $PID"

# 5. 等待启动并验证
echo "[5/5] 验证服务启动 ..."
for i in {1..10}; do
    sleep 1
    if curl -s "http://localhost:$PORT/api/curious/state" > /dev/null 2>&1; then
        echo ""
        echo "✅ Curious Agent 启动成功!"
        echo "   📍 API: http://localhost:$PORT/"
        echo "   🌐 Web UI: http://10.1.0.13:$PORT/"
        echo "   📝 日志: $LOG_FILE"
        exit 0
    fi
    echo "   ⏳ 尝试 $i/10 ..."
done

echo ""
echo "❌ 启动失败，请检查日志: $LOG_FILE"
exit 1
