#!/bin/bash
# 监控上下文限制日志
LOG_FILE="$HOME/xuzhi_genesis/logs/context_limiter.log"
echo "=== 上下文限制监控 ==="
echo "时间: $(date)"
if [ -f "$LOG_FILE" ]; then
    echo "最近被拒绝的操作:"
    grep "REJECT" "$LOG_FILE" | tail -5
    echo ""
    echo "最近允许的操作:"
    grep "ALLOW" "$LOG_FILE" | tail -5
else
    echo "日志文件不存在"
fi
