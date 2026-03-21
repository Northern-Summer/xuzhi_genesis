#!/bin/bash
#==============================================================================
# Lambda Watchdog — /home/summer/watchdog.sh
# 路径：~ (home directory) — 不受 /tmp 清理影响
# cron: */5 * * * *  (via openclaw cron, kind=systemEvent)
#==============================================================================

set -e

GATEWAY_URL="http://localhost:8765"
ALERT_FILE="/home/summer/.openclaw/workspace/memory/gateway_alert.json"
STATE_FILE="/home/summer/.openclaw/workspace/memory/gateway_state.json"
LOG_FILE="/home/summer/.openclaw/workspace/memory/gateway_watchdog.log"
TMPDIR="/home/summer/.openclaw/workspace/tmp"

# 确保目录存在
mkdir -p "$(dirname "$ALERT_FILE")" "$(dirname "$STATE_FILE")" "$(dirname "$LOG_FILE")" "$TMPDIR"

#==============================================================================
# Probe — 用 HTTP head，不启动 agentTurn，零 token 消耗
#==============================================================================
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$GATEWAY_URL/" 2>/dev/null || echo "000")

if [[ "$HTTP_CODE" == "200" ]]; then
    STATUS="HEALTHY"
    MSG="Gateway OK ($HTTP_CODE)"
else
    STATUS="DOWN"
    MSG="Gateway FAIL (HTTP $HTTP_CODE)"
fi

NOW=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
echo "[$NOW] $STATUS — $MSG" >> "$LOG_FILE"

# 只告警，不自动重启（重启由 self_heal.sh 负责）
if [[ "$STATUS" == "DOWN" ]]; then
    echo "["$NOW"] $MSG" >> "$ALERT_FILE"
fi

# 输出到 stdout（供 cron systemEvent 捕获）
echo "[$NOW] Lambda Watchdog: $MSG"

# 保护性检查：如果 workspace/tmp 被清空但 cron 引用它，告警
if [[ ! -d "$TMPDIR" ]] || [[ "$(ls -A "$TMPDIR" 2>/dev/null | wc -l)" -eq 0 ]]; then
    echo "[$NOW] WARNING: $TMPDIR is empty or missing (possible /tmp clear)" >> "$LOG_FILE"
fi
