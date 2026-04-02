#!/bin/bash
# 记忆增量同步 — 正确版本
# 2026-04-02 修正：只同步共享 L1 的每日文件，不覆盖 Agent 的私有记忆

set -e

SHARED_L1="$HOME/.xuzhi_memory/memory"
AGENTS_DIR="$HOME/.xuzhi_memory/agents"
AGENTS="phi delta theta gamma omega psi"
LOG_FILE="$HOME/.xuzhi_memory/memory_sync.log"

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "=== 记忆增量同步开始 ==="

# 只同步每日文件（YYYY-MM-DD.md 格式），不同步其他私有文件
TODAY=$(date +%Y-%m-%d)
TODAY_FILE="$SHARED_L1/$TODAY.md"

if [ -f "$TODAY_FILE" ]; then
  for agent in $AGENTS; do
    agent_memory_dir="$AGENTS_DIR/$agent/memory"
    agent_today="$agent_memory_dir/$TODAY.md"
    
    # 只同步今日文件，不覆盖其他私有文件
    if [ ! -f "$agent_today" ] || [ "$TODAY_FILE" -nt "$agent_today" ]; then
      cp "$TODAY_FILE" "$agent_today"
      log "同步今日文件: $agent/memory/$TODAY.md"
    fi
  done
  log "完成"
else
  log "今日文件不存在: $TODAY_FILE"
fi
