#!/bin/bash
# trigger_explore.sh - 触发 Curious Agent 定向探索
# Usage: bash trigger_explore.sh "主题" "上下文"
# Priority mode: bash trigger_explore.sh "主题" "上下文" priority

TOPIC="$1"
CONTEXT="${2:-}"
PRIORITY="${3:-}"

API_URL="http://localhost:4848/api/curious/inject"

if [ -z "$TOPIC" ]; then
    echo "Usage: $0 <topic> [context] [priority]"
    exit 1
fi

# 构建 JSON payload
PAYLOAD="{\"topic\":\"$TOPIC\""
if [ -n "$CONTEXT" ]; then
    PAYLOAD="$PAYLOAD,\"context\":\"$CONTEXT\""
fi
if [ "$PRIORITY" = "priority" ] || [ "$PRIORITY" = "true" ]; then
    PAYLOAD="$PAYLOAD,\"priority\":true"
fi
PAYLOAD="$PAYLOAD}"

curl -s -X POST "$API_URL" \
    -H "Content-Type: application/json" \
    -d "$PAYLOAD" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"
