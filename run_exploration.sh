#!/bin/bash
# Curious Agent 定时探索任务
# 每30分钟运行一次

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

export PYTHONPATH="$SCRIPT_DIR:$PYTHONPATH"
export BOCHA_API_KEY="***REMOVED***"

python3 curious_agent.py --run >> logs/curious.log 2>&1
