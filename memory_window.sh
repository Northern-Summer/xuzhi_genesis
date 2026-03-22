#!/bin/bash
#==============================================================================
# Sliding Memory Window — Λ
# 功能：保持 daily/ 文件总行数 ≤ MAX_LINES，超出则 FIFO 淘汰最旧条目
# 策略：只保留最近 N 个会话日的记忆，最古老的日期文件物理删除
#==============================================================================
set -euo pipefail

MAX_DAYS=7          # 保留最近 N 天的 daily 文件
MAX_LINES_PER_DAY=200  # 单日文件上限（防止单日爆炸）
MEMORY="$HOME/.xuzhi_memory"
LOG="$MEMORY/session_restore.log"

trim() {
    local file="$1"
    local max="$2"
    local lines=$(wc -l < "$file")
    if [ "$lines" -gt "$max" ]; then
        tail -n "$max" "$file" > "${file}.tmp" && mv "${file}.tmp" "$file"
        echo "[memory_window] TRIMMED $file: $lines → $max lines" >> "$LOG"
    fi
}

# 1. 裁剪单日超限文件
for f in "$MEMORY/daily"/*.md; do
    [ -f "$f" ] && trim "$f" "$MAX_LINES_PER_DAY"
done

# 2. 删除超期旧文件（FIFO）
DAYS_TO_KEEP=$(date -d "$MAX_DAYS days ago" '+%Y-%m-%d')
for f in "$MEMORY/daily"/*.md; do
    [ -f "$f" ] || continue
    fname=$(basename "$f" .md)
    # 只比较日期部分（去掉可能的额外后缀）
    date_part=$(echo "$fname" | cut -c1-10)
    if [[ "$date_part" < "$DAYS_TO_KEEP" ]]; then
        mv "$f" "$MEMORY/backup/archived_$(date +%Y%m%d_%H%M%S)_${fname}.md" 2>/dev/null || true
        echo "[memory_window] ARCHIVED old daily: $fname" >> "$LOG"
    fi
done

echo "[memory_window] done. retained days: ≤$MAX_DAYS, per-file: ≤$MAX_LINES_PER_DAY lines"
