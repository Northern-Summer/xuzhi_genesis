#!/bin/bash
# watchdog_timer.sh — 系统级 watchdog（不依赖 OpenClaw cron）
# 由 systemd timer 每分钟触发，检查 gateway 健康状态
# 如果 gateway 无响应超过阈值，触发自动恢复
# 2026-03-21

LOG="/tmp/watchdog_timer.log"
GATEWAY_PID=$(cat /tmp/openclaw_gateway.pid 2>/dev/null)
MAX_RESTARTS_PER_HOUR=3
WINDOW=3600

log() { echo "$(date +%H:%M:%S) [watchdog-timer] $1" | tee -a "$LOG"; }

# 检查 gateway 健康
check_gateway() {
    local status=$(openclaw gateway status 2>&1)
    if echo "$status" | grep -q "200"; then
        return 0  # 健康
    else
        return 1  # 不健康
    fi
}

# 记录重启次数（防止重启风暴）
record_restart() {
    local count_file="/tmp/watchdog_restart_count"
    local now=$(date +%s)
    # 清理超过1小时的旧记录
    mkdir -p /tmp
    touch "$count_file"
    local entries=$(cat "$count_file")
    local valid=""
    for ts in $entries; do
        if (( now - ts < WINDOW )); then
            valid="$valid $ts"
        fi
    done
    echo "$valid $now" > "$count_file"
    local count=$(echo $valid | wc -w)
    echo $((count + 1))
}

log "检查 gateway (pid=$GATEWAY_PID)..."
if check_gateway; then
    log "Gateway 健康 ✅"
    exit 0
fi

# Gateway 不健康
log "Gateway 不健康，尝试恢复..."
local restarts=$(record_restart)
log "过去1小时重启次数: $restarts"

if (( restarts > MAX_RESTARTS_PER_HOUR )); then
    log "⚠️ 重启过于频繁 ($restarts/$MAX_RESTARTS_PER_HOUR)，停止自动重启，请人工检查"
    exit 1
fi

# 尝试重启
log "执行 openclaw gateway restart..."
openclaw gateway restart 2>&1 | tee -a "$LOG"
sleep 8

if check_gateway; then
    log "✅ Gateway 恢复成功"
else
    log "❌ Gateway 仍然不健康，通知 Lambda"
    # 通知 Lambda（在 webchat 发送消息）
    echo "Gateway auto-recovery failed. Human intervention required." >&3
fi
