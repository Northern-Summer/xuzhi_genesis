#!/bin/bash
# 记忆一键推送 — L2更新 + 同步 + Git
# 工程改进铁律合规 — Ξ | 2026-03-31
# 自问：此操作是否让系统更安全/准确/优雅/高效？答案：YES

set -e

# 配置
SHARED_L1="$HOME/.xuzhi_memory/memory"
AGENTS_DIR="$HOME/.xuzhi_memory/agents"
MEMORY_MD="$HOME/.xuzhi_memory/agents/xi/MEMORY.md"
AGENTS="phi delta theta gamma omega psi"
TODAY=$(date +%Y-%m-%d)
NOW=$(date "+%Y-%m-%d %H:%M")

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}         记忆一键推送 | $NOW${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"

# Step 1: 同步共享 L1 → Agent 私有 L1
echo -e "\n${BLUE}[1/4] 同步共享 L1 → Agent 私有 L1${NC}"
SYNC_SCRIPT="$HOME/xuzhi_genesis/scripts/memory_sync.sh"
if [ -x "$SYNC_SCRIPT" ]; then
  bash "$SYNC_SCRIPT"
else
  echo -e "  ${YELLOW}⚠${NC} 同步脚本不存在或不可执行，跳过"
fi

# Step 2: 更新 MEMORY.md 时间戳
echo -e "\n${BLUE}[2/4] 更新 MEMORY.md 时间戳${NC}"
if [ -f "$MEMORY_MD" ]; then
  # 备份
  cp "$MEMORY_MD" "$MEMORY_MD.bak"
  
  # 更新时间戳（两种格式都处理）
  sed -i "s/当前时间.*/当前时间\": $TODAY $NOW GMT+8\"/" "$MEMORY_MD"
  sed -i "s/\*\*当前时间\*\*.*/\*\*当前时间\*\*: $TODAY $NOW GMT+8/" "$MEMORY_MD"
  sed -i "s/最后验证.*/最后验证\": $TODAY $NOW — Session End 执行完成\"/" "$MEMORY_MD"
  
  echo -e "  ${GREEN}✓${NC} MEMORY.md 时间戳已更新"
else
  echo -e "  ${RED}✗${NC} MEMORY.md 不存在"
  exit 1
fi

# Step 3: Git 提交 xuzhi_memory
echo -e "\n${BLUE}[3/4] Git 提交 xuzhi_memory${NC}"
cd "$HOME/.xuzhi_memory"

# 检查是否有更改
CHANGES=$(git status --porcelain | wc -l)
if [ "$CHANGES" -gt 0 ]; then
  echo -e "  发现 $CHANGES 个更改"
  git add -A
  git commit -m "chore: 记忆同步 $TODAY $NOW"
  echo -e "  ${GREEN}✓${NC} 已提交到本地仓库"
  
  # 推送到远程
  if git push 2>/dev/null; then
    echo -e "  ${GREEN}✓${NC} 已推送到远程"
  else
    echo -e "  ${YELLOW}⚠${NC} 推送失败（可能网络问题）"
  fi
else
  echo -e "  ${GREEN}✓${NC} 无更改需要提交"
fi

# Step 4: Git 提交 xuzhi_genesis
echo -e "\n${BLUE}[4/4] Git 提交 xuzhi_genesis${NC}"
cd "$HOME/xuzhi_genesis"

CHANGES=$(git status --porcelain | wc -l)
if [ "$CHANGES" -gt 0 ]; then
  echo -e "  发现 $CHANGES 个更改"
  git add -A
  git commit -m "chore: 记忆同步 $TODAY $NOW"
  echo -e "  ${GREEN}✓${NC} 已提交到本地仓库"
  
  if git push 2>/dev/null; then
    echo -e "  ${GREEN}✓${NC} 已推送到远程"
  else
    echo -e "  ${YELLOW}⚠${NC} 推送失败（可能网络问题）"
  fi
else
  echo -e "  ${GREEN}✓${NC} 无更改需要提交"
fi

# 完成
echo -e "\n${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✓ 推送完成${NC}"
echo ""
echo "下次使用："
echo "  同步检查:    bash ~/xuzhi_genesis/scripts/memory_health_check.sh"
echo "  手动同步:    bash ~/xuzhi_genesis/scripts/memory_sync.sh"
echo "  一键推送:    bash ~/xuzhi_genesis/scripts/memory_push.sh"
