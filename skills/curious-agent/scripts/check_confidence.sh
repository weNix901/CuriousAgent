#!/bin/bash
# check_confidence.sh - 检查 CA 知识图谱对某个话题的置信度
# Usage: bash scripts/check_confidence.sh "Transformer Attention机制"

TOPIC="$1"
API_URL="${CURIOUS_API_URL:-http://localhost:4848}"

if [ -z "$TOPIC" ]; then
    echo "Usage: $0 <topic>"
    exit 1
fi

RESPONSE=$(curl -s "${API_URL}/api/knowledge/confidence?topic=$(python3 -c "import urllib.parse; print(urllib.parse.quote('$TOPIC'))")")

echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"
