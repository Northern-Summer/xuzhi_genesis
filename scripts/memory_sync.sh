#!/bin/bash
# 记忆增量同步 — 共享L1 → Agent私有L1
# 工程改进铁律合规 — Ξ | 2026-03-31
# 自问：此操作是否让系统更安全/准确/优雅/高效？答案：YES

set -e

# 配置
SHARED_L1="$HOME/.xuzhi_memory/memory"
AGENTS_DIR="$HOME/.xuzhi_memory/agents"
AGENTS="phi delta theta gamma omega psi"
LOG_FILE="$HOME/.xuzhi_memory/memory_sync.log"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# dry-run 模式
DRY_RUN=false
if [ "$1" = "--dry-run" ] || [ "$1" = "-n" ]; then
  DRY_RUN=true
  log "${YELLOW}[DRY-RUN]${NC} 仅展示将要执行的操作，不实际执行"
fi

# 统计
SYNCED=0
SKIPPED=0
ERRORS=0

log "=== 记忆增量同步开始 ==="

# 遍历共享 L1 中的所有 daily 文件
for shared_file in "$SHARED_L1"/20*.md; do
  [ -f "$shared_file" ] || continue
  
  filename=$(basename "$shared_file")
  shared_checksum=$(md5sum "$shared_file" 2>/dev/null | cut -d' ' -f1)
  
  # 同步到每个 agent
  for agent in $AGENTS; do
    agent_memory_dir="$AGENTS_DIR/$agent/memory"
    agent_file="$agent_memory_dir/$filename"
    
    # 确保 agent memory 目录存在
    if [ ! -d "$agent_memory_dir" ]; then
      if [ "$DRY_RUN" = true ]; then
        log "${YELLOW}[DRY-RUN]${NC} 将创建目录: $agent_memory_dir"
      else
        mkdir -p "$agent_memory_dir"
        log "${GREEN}✓${NC} 创建目录: $agent_memory_dir"
      fi
    fi
    
    # 检查是否需要同步
    if [ -f "$agent_file" ]; then
      agent_checksum=$(md5sum "$agent_file" 2>/dev/null | cut -d' ' -f1)
      
      if [ "$shared_checksum" = "$agent_checksum" ]; then
        # 内容相同，跳过
        SKIPPED=$((SKIPPED + 1))
        continue
      else
        # 内容不同，需要更新
        if [ "$DRY_RUN" = true ]; then
          log "${YELLOW}[DRY-RUN]${NC} 将更新: $agent/memory/$filename (内容已变化)"
        else
          # 备份原文件
          cp "$agent_file" "$agent_file.bak"
          # 复制新内容
          cp "$shared_file" "$agent_file"
          log "${GREEN}✓${NC} 更新: $agent/memory/$filename"
          SYNCED=$((SYNCED + 1))
        fi
      fi
    else
      # 文件不存在，需要创建
      if [ "$DRY_RUN" = true ]; then
        log "${YELLOW}[DRY-RUN]${NC} 将创建: $agent/memory/$filename"
      else
        cp "$shared_file" "$agent_file"
        log "${GREEN}✓${NC} 创建: $agent/memory/$filename"
        SYNCED=$((SYNCED + 1))
      fi
    fi
  done
done

# 同步 INFRASTRUCTURE.md（如果存在）
infra_file="$SHARED_L1/INFRASTRUCTURE.md"
if [ -f "$infra_file" ]; then
  for agent in $AGENTS; do
    agent_memory_dir="$AGENTS_DIR/$agent/memory"
    agent_infra="$agent_memory_dir/INFRASTRUCTURE.md"
    
    if [ ! -f "$agent_infra" ]; then
      if [ "$DRY_RUN" = true ]; then
        log "${YELLOW}[DRY-RUN]${NC} 将创建: $agent/memory/INFRASTRUCTURE.md"
      else
        cp "$infra_file" "$agent_infra"
        log "${GREEN}✓${NC} 创建: $agent/memory/INFRASTRUCTURE.md"
      fi
    fi
  done
fi

# 汇总
log "=== 同步完成 ==="
log "同步: $SYNCED 个文件"
log "跳过: $SKIPPED 个文件（内容相同）"

if [ "$DRY_RUN" = true ]; then
  log "${YELLOW}[DRY-RUN]${NC} 以上为预览，未实际执行"
  log "执行实际同步: $0"
fi

exit 0
