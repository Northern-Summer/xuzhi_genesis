#!/bin/bash
# 记忆健康检查 — 系统级强制检查
# 工程改进铁律合规 — Ξ | 2026-03-31
# 自问：此操作是否让系统更安全/准确/优雅/高效？答案：YES

set -e

# 配置
SHARED_L1="$HOME/.xuzhi_memory/memory"
AGENTS_DIR="$HOME/.xuzhi_memory/agents"
MEMORY_MD="$HOME/.xuzhi_memory/agents/xi/MEMORY.md"
AGENTS="phi delta theta gamma omega psi"
TODAY=$(date +%Y-%m-%d)

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

ERRORS=0
WARNINGS=0

echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}         记忆系统健康检查 | $TODAY $(date +%H:%M)${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"

# 检查 1: 今日共享 L1 文件是否存在
echo -e "\n${BLUE}[1/6] 共享 L1 每日文件检查${NC}"
TODAY_FILE="$SHARED_L1/$TODAY.md"
if [ -f "$TODAY_FILE" ]; then
  LINES=$(wc -l < "$TODAY_FILE")
  if [ "$LINES" -lt 50 ]; then
    echo -e "  ${YELLOW}⚠${NC} 今日文件过短: $LINES 行"
    WARNINGS=$((WARNINGS + 1))
  else
    echo -e "  ${GREEN}✓${NC} 今日文件存在: $LINES 行"
  fi
else
  echo -e "  ${RED}✗${NC} 今日文件不存在: $TODAY_FILE"
  ERRORS=$((ERRORS + 1))
fi

# 检查 2: Agent 私有 L1 同步状态
echo -e "\n${BLUE}[2/6] Agent 私有 L1 同步检查${NC}"
for agent in $AGENTS; do
  agent_memory="$AGENTS_DIR/$agent/memory"
  
  if [ ! -d "$agent_memory" ]; then
    echo -e "  ${RED}✗${NC} $agent: memory 目录不存在"
    ERRORS=$((ERRORS + 1))
    continue
  fi
  
  # 检查今日文件是否同步
  agent_today="$agent_memory/$TODAY.md"
  shared_today="$SHARED_L1/$TODAY.md"
  
  if [ -f "$shared_today" ]; then
    if [ -f "$agent_today" ]; then
      shared_md5=$(md5sum "$shared_today" 2>/dev/null | cut -d' ' -f1)
      agent_md5=$(md5sum "$agent_today" 2>/dev/null | cut -d' ' -f1)
      
      if [ "$shared_md5" = "$agent_md5" ]; then
        echo -e "  ${GREEN}✓${NC} $agent: 已同步"
      else
        echo -e "  ${YELLOW}⚠${NC} $agent: 内容不同步 (运行 memory_sync.sh)"
        WARNINGS=$((WARNINGS + 1))
      fi
    else
      echo -e "  ${RED}✗${NC} $agent: 缺少今日文件"
      ERRORS=$((ERRORS + 1))
    fi
  fi
done

# 检查 3: 过去 3 天同步状态
echo -e "\n${BLUE}[3/6] 近3天同步状态检查${NC}"
for i in 1 2 3; do
  DATE=$(date -d "$TODAY -$i days" +%Y-%m-%d)
  SHARED_FILE="$SHARED_L1/$DATE.md"
  
  if [ -f "$SHARED_FILE" ]; then
    MISSING_AGENTS=""
    for agent in $AGENTS; do
      if [ ! -f "$AGENTS_DIR/$agent/memory/$DATE.md" ]; then
        MISSING_AGENTS="$MISSING_AGENTS $agent"
      fi
    done
    
    if [ -n "$MISSING_AGENTS" ]; then
      echo -e "  ${YELLOW}⚠${NC} $DATE: 缺失 agent:$MISSING_AGENTS"
      WARNINGS=$((WARNINGS + 1))
    else
      echo -e "  ${GREEN}✓${NC} $DATE: 全部同步"
    fi
  fi
done

# 检查 4: MEMORY.md 时间戳
echo -e "\n${BLUE}[4/6] L2 MEMORY.md 时间戳检查${NC}"
if [ -f "$MEMORY_MD" ]; then
  # 提取时间戳（格式：2026-03-31 21:09 GMT+8）
  LAST_TS=$(grep -oP '(?<=当前时间": )[0-9-]+' "$MEMORY_MD" 2>/dev/null | head -1)
  
  if [ -n "$LAST_TS" ]; then
    DAYS_OLD=$(( ($(date +%s) - $(date -d "$LAST_TS" +%s 2>/dev/null || echo 0)) / 86400 ))
    
    if [ "$DAYS_OLD" -gt 7 ]; then
      echo -e "  ${RED}✗${NC} 时间戳过时: $DAYS_OLD 天 (>7天)"
      ERRORS=$((ERRORS + 1))
    elif [ "$DAYS_OLD" -gt 3 ]; then
      echo -e "  ${YELLOW}⚠${NC} 时间戳较旧: $DAYS_OLD 天"
      WARNINGS=$((WARNINGS + 1))
    else
      echo -e "  ${GREEN}✓${NC} 时间戳正常: $DAYS_OLD 天前"
    fi
  else
    echo -e "  ${YELLOW}⚠${NC} 无法解析时间戳"
    WARNINGS=$((WARNINGS + 1))
  fi
else
  echo -e "  ${RED}✗${NC} MEMORY.md 不存在"
  ERRORS=$((ERRORS + 1))
fi

# 检查 5: Git 状态
echo -e "\n${BLUE}[5/6] Git 状态检查${NC}"
cd "$HOME/.xuzhi_memory"
UNCOMMITTED=$(git status --porcelain 2>/dev/null | wc -l)
if [ "$UNCOMMITTED" -gt 10 ]; then
  echo -e "  ${YELLOW}⚠${NC} xuzhi_memory: $UNCOMMITTED 个未提交更改"
  WARNINGS=$((WARNINGS + 1))
elif [ "$UNCOMMITTED" -gt 0 ]; then
  echo -e "  ${GREEN}✓${NC} xuzhi_memory: $UNCOMMITTED 个未提交更改（正常）"
else
  echo -e "  ${GREEN}✓${NC} xuzhi_memory: 工作目录干净"
fi

cd "$HOME/xuzhi_genesis"
UNCOMMITTED=$(git status --porcelain 2>/dev/null | wc -l)
if [ "$UNCOMMITTED" -gt 10 ]; then
  echo -e "  ${YELLOW}⚠${NC} xuzhi_genesis: $UNCOMMITTED 个未提交更改"
  WARNINGS=$((WARNINGS + 1))
else
  echo -e "  ${GREEN}✓${NC} xuzhi_genesis: $UNCOMMITTED 个未提交更改"
fi

# 检查 6: 关键文件存在性
echo -e "\n${BLUE}[6/6] 关键文件检查${NC}"
CRITICAL_FILES=(
  "$HOME/.xuzhi_memory/manifests/SOUL_IMMUTABLE.md"
  "$HOME/.xuzhi_memory/manifests/constitutional_core.md"
  "$HOME/.xuzhi_memory/agents/xi/SOUL.md"
  "$HOME/.xuzhi_memory/agents/xi/IDENTITY.md"
)

for f in "${CRITICAL_FILES[@]}"; do
  if [ -f "$f" ]; then
    echo -e "  ${GREEN}✓${NC} $(basename $f)"
  else
    echo -e "  ${RED}✗${NC} $(basename $f) 不存在"
    ERRORS=$((ERRORS + 1))
  fi
done

# 汇总
echo -e "\n${BLUE}═══════════════════════════════════════════════════════════${NC}"
if [ "$ERRORS" -gt 0 ]; then
  echo -e "${RED}✗ 发现 $ERRORS 个错误，$WARNINGS 个警告${NC}"
  echo -e "${YELLOW}建议操作：${NC}"
  echo "  1. 运行 memory_sync.sh 同步缺失文件"
  echo "  2. 运行 memory_push.sh 更新 L2 时间戳"
  exit 1
elif [ "$WARNINGS" -gt 0 ]; then
  echo -e "${YELLOW}⚠ $WARNINGS 个警告，建议检查${NC}"
  exit 0
else
  echo -e "${GREEN}✓ 记忆系统健康${NC}"
  exit 0
fi
