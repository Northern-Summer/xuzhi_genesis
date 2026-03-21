#!/bin/bash
# ~/.xuzhi_lessons.sh — 每次唤醒必须执行
# 显示最近教训，强制看一遍，不许跳过

LESSONS="/home/summer/.xuzhi_lessons.md"
CHECKPOINT="/home/summer/.xuzhi_checkpoint.json"

echo "========================================"
echo "  Xuzhi 教训账本 — $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "========================================"
echo ""

if [[ -f "$LESSONS" ]]; then
    # 显示最近3条教训
    echo "【最近教训】"
    grep -E "^## L[0-9]+" "$LESSONS" | tail -5
    echo ""
    echo "【当前状态快照】"
    python3 -c "
import json, sys
with open('$CHECKPOINT') as f:
    c = json.load(f)
print(f\"Gateway: {c['gateway']['status']}\")
print(f\"Scripts OK: {[k for k in c['scripts'] if not __import__('os').path.exists(c['scripts'][k])]}\")
print(f\"Recovery: {c['recovery_action']}\")
" 2>/dev/null || echo "(checkpoint 读取失败)"
else
    echo "WARNING: $LESSONS 不存在！"
fi

echo ""
echo "【禁止事项】"
echo "  - 不要依赖 workspace/tmp/ 的任何脚本"
echo "  - 不要相信 cron 列表没被 Gateway 重启还原"
echo "  - 不要在 commit 之前做任何不可逆的修改"
echo ""
echo "【如果 exec 超时/失败】→ 写日志到 memory/YYYY-MM-DD.md，不继续"
echo "========================================"
