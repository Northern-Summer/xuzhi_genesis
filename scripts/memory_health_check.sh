#!/bin/bash
# 记忆健康检查 — 2026-04-02 正确版本
# 私有 L2 不同步，每个 Agent 自己管理

set -e

SHARED_L1="$HOME/.xuzhi_memory/memory"
TODAY=$(date +%Y-%m-%d)

echo "═══════════════════════════════════════════════════════════"
echo "         记忆系统健康检查 | $TODAY $(date +%H:%M)"
echo "═══════════════════════════════════════════════════════════"

# 检查共享 L1
TODAY_FILE="$SHARED_L1/$TODAY.md"
if [ -f "$TODAY_FILE" ]; then
  LINES=$(wc -l < "$TODAY_FILE")
  echo "✓ 共享 L1 今日文件: $LINES 行"
else
  echo "✗ 共享 L1 今日文件不存在"
  exit 1
fi

# 检查私有 L2 目录是否存在（不检查内容）
for agent in phi delta theta gamma omega psi rho sigma; do
  if [ "$agent" = "rho" ]; then
    dir="$HOME/.openclaw/agents/rho/workspace/memory"
  elif [ "$agent" = "sigma" ]; then
    dir="$HOME/.openclaw/agents/sigma/workspace/memory"
  else
    dir="$HOME/.xuzhi_memory/agents/$agent/memory"
  fi
  
  if [ -d "$dir" ]; then
    count=$(ls "$dir" 2>/dev/null | wc -l)
    echo "✓ $agent 私有 L2 目录存在 ($count 文件)"
  else
    echo "⚠ $agent 私有 L2 目录不存在，已创建"
    mkdir -p "$dir"
  fi
done

echo "═══════════════════════════════════════════════════════════"
echo "✅ 检查完成"
