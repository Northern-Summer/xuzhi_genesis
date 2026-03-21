#!/bin/bash
# OpenClaw Agent Rename — 宪法合规化
# 将 OpenClaw agent ID 对齐到 Xuzhi 宪法命名
# 原则：OpenClaw shell 适配 Xuzhi 灵魂，绝不相反

set -e
LOG="~/.openclaw/rename.log"
echo "[rename] 开始 $(date)" >> $LOG

# 1. scientist → xuzhi-theta-seeker
echo "[rename] scientist → xuzhi-theta-seeker" >> $LOG
openclaw agents rename scientist xuzhi-theta-seeker 2>&1 >> $LOG && echo "✓ scientist → xuzhi-theta-seeker" || echo "✗ rename failed (see log)"

# 2. engineer → xuzhi-phi  
echo "[rename] engineer → xuzhi-phi" >> $LOG
openclaw agents rename engineer xuzhi-phi 2>&1 >> $LOG && echo "✓ engineer → xuzhi-phi" || echo "✗ rename failed (see log)"

# 3. philosopher → xuzhi-psi
echo "[rename] philosopher → xuzhi-psi" >> $LOG
openclaw agents rename philosopher xuzhi-psi 2>&1 >> $LOG && echo "✓ philosopher → xuzhi-psi" || echo "✗ rename failed (see log)"

# 4. 验证
echo "[rename] 验证结果:" >> $LOG
openclaw agents list 2>&1 >> $LOG

echo "[rename] 完成 $(date)" >> $LOG
cat $LOG
