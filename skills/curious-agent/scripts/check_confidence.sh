#!/bin/bash
# check_confidence.sh - 检查 R1D3 对某个主题的置信度
# Usage: bash check_confidence.sh "主题关键词"

TOPIC="$1"
API_URL="http://localhost:4848/api/metacognitive/check"

if [ -z "$TOPIC" ]; then
    echo "Usage: $0 <topic>"
    exit 1
fi

RESPONSE=$(curl -s "${API_URL}?topic=$(python3 -c "import urllib.parse; print(urllib.parse.quote('$TOPIC'))")")

echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"
