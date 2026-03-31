#!/bin/bash
# 系统一致性检查 — 每周运行，发现混乱点
# 工程改进铁律合规 — Ξ | 2026-03-31
# 自问：此操作是否让系统更安全/准确/优雅/高效？答案：YES

set -e

LOG_FILE="$HOME/.xuzhi_memory/system_consistency.log"
ERRORS=0
WARNINGS=0

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

echo "═══════════════════════════════════════════════════════════" | tee -a "$LOG_FILE"
echo "       系统一致性检查 | $(date '+%Y-%m-%d %H:%M')" | tee -a "$LOG_FILE"
echo "═══════════════════════════════════════════════════════════" | tee -a "$LOG_FILE"

# 1. 检查 AGENTS.md 重复
log "\n[1/5] AGENTS.md 一致性检查"
for agent in phi delta theta gamma omega psi; do
  ws=$(head -1 ~/.openclaw/agents/$agent/workspace/AGENTS.md 2>/dev/null)
  xm=$(head -1 ~/.xuzhi_memory/agents/$agent/AGENTS.md 2>/dev/null)
  if [ "$ws" != "$xm" ]; then
    log "  ⚠️ $agent: workspace 和 xuzhi_memory 的 AGENTS.md 不同"
    log "    workspace: $ws"
    log "    xuzhi_memory: $xm"
    WARNINGS=$((WARNINGS + 1))
  else
    log "  ✅ $agent: 一致"
  fi
done

# 2. 检查 HEARTBEAT.md 轮值检查
log "\n[2/5] HEARTBEAT.md 轮值检查"
for agent in phi delta theta gamma omega psi; do
  count=$(grep -c "轮值\|ON_DUTY\|当值" ~/.openclaw/agents/$agent/workspace/HEARTBEAT.md 2>/dev/null || echo "0")
  if [ "$count" -lt 1 ]; then
    log "  ❌ $agent: 缺少轮值检查逻辑"
    ERRORS=$((ERRORS + 1))
  else
    log "  ✅ $agent: 有轮值检查"
  fi
done

# 3. 检查脚本重复
log "\n[3/5] 脚本重复检查"
duplicates=$(find ~/.openclaw ~/.xuzhi_memory ~/xuzhi_genesis -name "*.sh" -type f 2>/dev/null | xargs -I{} basename {} | sort | uniq -c | sort -rn | awk '$1 > 1 {print $0}')
if [ -n "$duplicates" ]; then
  log "  ⚠️ 发现重复脚本:"
  echo "$duplicates" | head -5 | while read line; do
    log "    $line"
  done
  WARNINGS=$((WARNINGS + 1))
else
  log "  ✅ 无重复脚本"
fi

# 4. 检查模型配置一致性
log "\n[4/5] 模型配置检查"
main_model=$(grep '"model"' ~/.openclaw/agents/main.json 2>/dev/null | head -1)
for agent in phi delta theta gamma omega psi; do
  agent_model=$(grep '"model"' ~/.openclaw/agents/$agent.json 2>/dev/null | head -1)
  if [ "$agent_model" != "$main_model" ] && [ -n "$agent_model" ]; then
    log "  ⚠️ $agent 模型与 main 不同: $agent_model"
    WARNINGS=$((WARNINGS + 1))
  fi
done
log "  ✅ 模型配置检查完成"

# 5. 检查关键文件存在性
log "\n[5/5] 关键文件检查"
critical_files=(
  "$HOME/.xuzhi_memory/manifests/SYSTEM_ARCHITECTURE_SPEC.md"
  "$HOME/.xuzhi_memory/manifests/MEMORY_SYSTEM_SPEC.md"
  "$HOME/xuzhi_genesis/scripts/memory_sync.sh"
  "$HOME/xuzhi_genesis/scripts/memory_health_check.sh"
)
for f in "${critical_files[@]}"; do
  if [ -f "$f" ]; then
    log "  ✅ $(basename $f)"
  else
    log "  ❌ 缺失: $f"
    ERRORS=$((ERRORS + 1))
  fi
done

# 汇总
log "\n═══════════════════════════════════════════════════════════"
if [ "$ERRORS" -gt 0 ]; then
  log "❌ 发现 $ERRORS 个错误，$WARNINGS 个警告"
  log "建议：运行修复脚本或手动处理"
  exit 1
elif [ "$WARNINGS" -gt 0 ]; then
  log "⚠️ $WARNINGS 个警告，建议检查"
  exit 0
else
  log "✅ 系统一致性检查通过"
  exit 0
fi
