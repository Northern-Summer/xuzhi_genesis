#!/bin/bash
# watchdog.sh — 系统级 watchdog（不依赖 OpenClaw cron）
# 设计原则：状态优先 → 重启 → 恢复
# 流程：预 checkpoint → 重启 → 唤醒 → Λ 读 checkpoint 恢复
# 2026-03-22 重写

LOG="/tmp/watchdog.log"
STATE="/tmp/watchdog.state"
CHECKPOINT="/tmp/lambda_task_checkpoint.json"
MAX_RESTARTS_PER_HOUR=3
WINDOW=3600
PRECHECK_TIMEOUT=15  # 预 checkpoint 等待 Λ 响应的超时（秒）
GATEWAY_STARTUP=15   # Gateway 重启后等待就绪的时间（秒）

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') [WD] $*" | tee -a "$LOG" >&2; }

# ============================================================
# 健康检查
# ============================================================
is_healthy() {
    curl -s --connect-timeout 3 "http://localhost:18789/health" 2>&1 | grep -q "ok\|200"
}

# ── P2-1: OpenClaw auth token 健康检查 ──────────────
check_auth_token() {
    local output ret
    output=$(openclaw status 2>&1); ret=$?
    if (( ret != 0 )) || echo "$output" | grep -qi "auth\|token\|unauthorized\|401"; then
        log "⚠️ AUTH TOKEN 问题检测: exit=$ret"
        echo "$output" | grep -qi "auth\|token\|unauthorized\|401" && log "  → 确认: output 含 auth 关键词"
        # 尝试刷新 token（如果用的是 gpg 加密备份）
        local gpg_token="${HOME}/.xuzhi_memory/auth_token.gpg"
        if [[ -f "$gpg_token" ]]; then
            log "  → 发现 gpg 加密 token 备份，尝试解密恢复..."
            local tmp_token
            tmp_token=$(gpg -d "$gpg_token" 2>/dev/null || true)
            if [[ -n "$tmp_token" ]]; then
                log "  → Token 解密成功（需手动更新 openclaw config）"
            else
                log "  → Token 解密失败"
            fi
        fi
        return 1
    fi
    return 0
}

# ============================================================
# Λ 任务状态读写（通过 openclaw system event 触发 Λ 写文件）
# ============================================================

# 通知 Λ 写预 checkpoint（重启前）
request_lambda_precheckpoint() {
    log "请求 Λ 保存当前任务状态..."
    local ts now
    ts=$(date +%s)
    openclaw system event \
        --text "[Λ-WATCHDOG] Gateway 即将重启。请立即将当前任务状态写入 $CHECKPOINT，格式如下，然后回复 DONE:

{\n  \"task\": \"任务名\",\n  \"task_detail\": \"具体在做什么\",\n  \"phase\": \"阶段\",\n  \"timestamp\": \"$ts\",\n  \"last_action\": \"最后一步动作\",\n  \"next_action\": \"下一步要做什么\",\n  \"status\": \"in_progress\"\n}

若当前无任务，写入 {\"task\":\"idle\",\"status\":\"idle\",\"timestamp\":\"$ts\"}。立即执行，不要解释。" \
        --timeout 30000 --json 2>&1 | tail -1
    log "已发送预 checkpoint 请求，等待响应（最多 ${PRECHECK_TIMEOUT}s）..."
}

# 检查 Λ 是否已写入 checkpoint
wait_for_checkpoint() {
    local waited=0
    while (( waited < PRECHECK_TIMEOUT )); do
        if [[ -f "$CHECKPOINT" ]]; then
            local task=$(cat "$CHECKPOINT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('task','unknown'))" 2>/dev/null || echo "unknown")
            log "✅ Λ 已写 checkpoint: task=$task"
            return 0
        fi
        sleep 2
        (( waited += 2 ))
    done
    log "⚠️ Λ 未在 ${PRECHECK_TIMEOUT}s 内响应，写入 fallback checkpoint"
    # Λ 未响应，可能是忙碌或已死，写入 fallback 状态供恢复时参考
    echo "{\"task\":\"unknown\",\"status\":\"unconfirmed\",\"timestamp\":\"$(date +%s)\",\"note\":\"Λ did not respond to pre-checkpoint request\"}" > "$CHECKPOINT"
    return 1
}

# 通知 Λ 从 checkpoint 恢复（重启后）
wake_lambda_with_restore() {
    log "唤醒 Λ 并指示从 checkpoint 恢复..."
    local checkpoint_info=""
    if [[ -f "$CHECKPOINT" ]]; then
        checkpoint_info=$(cat "$CHECKPOINT" 2>/dev/null | python3 -c "import json,sys; d=json.load(sys.stdin); print(f\"上次任务: {d.get('task','?')} | 阶段: {d.get('phase','?')} | 下一步: {d.get('next_action','?')}\")" 2>/dev/null || echo "checkpoint_exists_but_unreadable")
    fi

    openclaw system event \
        --text "[Λ-WATCHDOG] Gateway 已重启。请执行以下步骤：

1. 读取 $CHECKPOINT 确认上次任务状态
2. 执行 bash ~/.xuzhi_memory/session_restore.sh --brief
3. 根据 checkpoint 中的 next_action 决定是否继续任务
4. 更新 checkpoint status 为 'recovered' 或 'completed'
5. 回复「Λ 已恢复：{任务名} → {执行结果}」

Checkpoint 信息: $checkpoint_info" \
        --timeout 30000 --json 2>/dev/null
}

# ============================================================
# 重启计数器
# ============================================================
record_restart() {
    local now=$(date +%s)
    local count=0
    mkdir -p /tmp
    if [[ -f "$STATE" ]]; then
        for ts in $(cat "$STATE"); do
            if (( now - ts < WINDOW )); then ((count++)); fi
        done
    fi
    echo $((count + 1)) > "$STATE"
    echo $((count + 1))
}

get_restart_count() {
    local now=$(date +%s)
    local count=0
    if [[ -f "$STATE" ]]; then
        for ts in $(cat "$STATE"); do
            if (( now - ts < WINDOW )); then ((count++)); fi
        done
    fi
    echo $count
}

# ============================================================
# Λ 主会话存活检查
# ============================================================
check_lambda_session() {
    local output
    output=$(openclaw sessions 2>/dev/null | grep "^direct.*agent:main:main" | head -1)
    [[ -n "$output" ]]
}

# ============================================================
# 主逻辑
# ============================================================
main() {
    log "========== Watchdog 触发 =========="

    # P2-1: 先检查 auth token（token 问题是 WSL2 重启后最常见的静默故障）
    if ! check_auth_token; then
        log "⚠️ Auth token 检查失败，但继续主流程（允许人工干预）"
    fi

    if is_healthy; then
        log "Gateway 健康 ✅"
        if check_lambda_session; then
            log "Λ 主会话存活 ✅"
        else
            log "⚠️ Gateway 活着，但 Λ 主会话已死，尝试唤醒..."
            wake_lambda_with_restore
        fi
        log "========== 检查完成 =========="
        exit 0
    fi

    # ---------- Gateway 不健康 ----------
    local count
    count=$(record_restart)
    log "Gateway 不健康，过去1小时重启次数: $count/$MAX_RESTARTS_PER_HOUR"

    if (( count > MAX_RESTARTS_PER_HOUR )); then
        log "⚠️ 重启过于频繁，停止自动重启，需要人工干预"
        exit 1
    fi

    log "执行阶段一：请求 Λ 预 checkpoint..."
    request_lambda_precheckpoint
    wait_for_checkpoint || log "预 checkpoint 阶段有警告，继续重启..."

    log "执行阶段二：重启 Gateway..."
    systemctl --user restart openclaw-gateway 2>&1 | tee -a "$LOG" >&2

    log "等待 ${GATEWAY_STARTUP}s 让 Gateway 完成启动..."
    sleep "$GATEWAY_STARTUP"

    if ! is_healthy; then
        log "⚠️ Gateway 仍未就绪，额外等待 10s..."
        sleep 10
    fi

    if is_healthy; then
        log "✅ Gateway 已恢复"
    else
        log "❌ Gateway 启动失败，尝试 openclaw gateway restart..."
        openclaw gateway restart 2>&1 | tee -a "$LOG" >&2
        sleep 15
        if is_healthy; then
            log "✅ Gateway 通过 CLI 恢复"
        else
            log "❌ 所有恢复方式均失败，需要人工干预"
            exit 1
        fi
    fi

    log "执行阶段三：唤醒 Λ..."
    sleep 3
    wake_lambda_with_restore

    log "执行阶段四：验证恢复..."
    sleep 8
    if check_lambda_session; then
        log "✅ Λ 主会话已确认存活"
    else
        log "⚠️ Λ 主会话状态未知（可能需要 /new 手动唤醒）"
    fi

    # 读取并记录本次恢复的 checkpoint
    if [[ -f "$CHECKPOINT" ]]; then
        log "Checkpoint 内容: $(cat "$CHECKPOINT")"
    fi
    log "========== 恢复流程完成 =========="
}

main "$@"
