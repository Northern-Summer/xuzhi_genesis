#!/bin/bash
# watchdog.sh — 系统级 watchdog（不依赖 OpenClaw cron）
# 用普通用户权限，通过 cron 每分钟检查一次
# 将 pid 写入文件，如果需要重启由 watchdog 自己触发（不需要 sudo）
# 2026-03-21

LOG="/tmp/watchdog.log"
STATE="/tmp/watchdog.state"
MAX_RESTARTS_PER_HOUR=3
WINDOW=3600

# 日志函数（输出到 stderr，cron 只捕获 stdout）
log() { echo "$(date '+%Y-%m-%d %H:%M:%S') [WD] $1" | tee -a "$LOG" >&2; }

# 检查 gateway 健康
is_healthy() {
    local status
    status=$(openclaw gateway status 2>&1)
    echo "$status" | grep -q "200\|healthy\|running"
}

# 读取并更新重启计数器
get_restart_count() {
    local now=$(date +%s)
    local count=0
    if [[ -f "$STATE" ]]; then
        local lines=$(cat "$STATE")
        for ts in $lines; do
            if (( now - ts < WINDOW )); then
                ((count++))
            fi
        done
    fi
    echo $count
}

record_restart() {
    local now=$(date +%s)
    local count=0
    mkdir -p /tmp
    if [[ -f "$STATE" ]]; then
        local lines=$(cat "$STATE")
        for ts in $lines; do
            if (( now - ts < WINDOW )); then
                ((count++))
            fi
        done
    fi
    echo $((count + 1)) > "$STATE"
    echo $((count + 1))
}

log "检查 gateway..."
if is_healthy; then
    log "Gateway 健康 ✅"
    exit 0
fi

# Gateway 不健康
log "Gateway 不健康，尝试恢复..."
local count=$(record_restart)
log "过去1小时重启次数: $count"

if (( count > MAX_RESTARTS_PER_HOUR )); then
    log "⚠️ 重启过于频繁 ($count/$MAX_RESTARTS_PER_HOUR)，停止自动重启"
    exit 1
fi

# 尝试重启（通过 systemd）
log "执行 systemctl --user restart openclaw..."
systemctl --user restart openclaw 2>&1 | tee -a "$LOG" >&2
sleep 8

if is_healthy; then
    log "✅ Gateway 恢复成功"
else
    log "❌ Gateway 仍然不健康，尝试 openclaw gateway restart..."
    openclaw gateway restart 2>&1 | tee -a "$LOG" >&2
    sleep 10
    if is_healthy; then
        log "✅ Gateway 通过 openclaw CLI 恢复成功"
    else
        log "❌ 所有恢复方式均失败，需要人工干预"
    fi
fi
