#!/bin/bash
# openclaw_rename.sh — OpenClaw Agent ID 合宪化
# 原则：OpenClaw shell 适配 Xuzhi 灵魂，绝不相反
# 操作：直接修改 gateway.json 的 agent ID 映射
# 2026-03-21

set -e
GATEWAY="/usr/local/share/.config/yarn/global/node_modules/openclaw/data/gateway.json"
BACKUP="/tmp/gateway.json.backup.$(date +%s)"

echo "=== OpenClaw Agent 合宪化 ==="

# 备份
cp "$GATEWAY" "$BACKUP"
echo "✓ 备份: $BACKUP"

# 确认当前状态
echo ""
echo "当前 agent 列表:"
grep -o '"[^"]*": {"workspace"' "$GATEWAY" | sed 's/: {"workspace//' | sed 's/"//g' | sort

# Rename 映射
echo ""
echo "执行 rename:"
echo "  scientist       → xuzhi-theta-seeker"
echo "  engineer        → xuzhi-phi"
echo "  philosopher     → xuzhi-psi"
echo "  xuzhi-philosopher → (将检查是否冗余)"
echo "  xuzhi-engineer  → (将检查是否冗余)"

# 执行 sed replace（直接在备份文件上操作，然后替换原文件）
cp "$BACKUP" "$GATEWAY"

# 1. scientist → xuzhi-theta-seeker
sed -i 's/"scientist":/"xuzhi-theta-seeker":/g' "$GATEWAY"
echo "✓ scientist → xuzhi-theta-seeker"

# 2. engineer → xuzhi-phi
sed -i 's/"engineer":/"xuzhi-phi":/g' "$GATEWAY"
echo "✓ engineer → xuzhi-phi"

# 3. philosopher → xuzhi-psi  
sed -i 's/"philosopher":/"xuzhi-psi":/g' "$GATEWAY"
echo "✓ philosopher → xuzhi-psi"

# 验证
echo ""
echo "修改后 agent 列表:"
grep -o '"[^"]*": {"workspace"' "$GATEWAY" | sed 's/: {"workspace//' | sed 's/"//g' | sort

# 重启 gateway 使配置生效
echo ""
echo "重启 gateway..."
sudo systemctl restart openclaw 2>/dev/null || sudo openclaw gateway restart 2>/dev/null || openclaw gateway restart 2>/dev/null
echo "✓ gateway 已重启（如果命令失败请手动重启）"

echo ""
echo "=== 完成 ==="
echo "检查权限: sudo chmod 644 $GATEWAY 如果需要"
