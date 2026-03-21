#!/usr/bin/env python3
# openclaw_rename.py — OpenClaw Agent ID 合宪化
# 直接修改 gateway.json 的 agent ID 键
# 原则：OpenClaw shell 适配 Xuzhi 灵魂，绝不相反
# 2026-03-21

import json
import shutil
import sys
import subprocess
from pathlib import Path

GATEWAY = Path("/usr/local/share/.config/yarn/global/node_modules/openclaw/data/gateway.json")
BACKUP = Path(f"/tmp/gateway.json.backup.{int(subprocess.time.time())}")

# Rename 映射：旧ID → 新ID
RENAME_MAP = {
    "scientist": "xuzhi-theta-seeker",
    "engineer": "xuzhi-phi",
    "philosopher": "xuzhi-psi",
}

print("=== OpenClaw Agent 合宪化 ===")
print(f"Gateway: {GATEWAY}")

# 备份
shutil.copy2(GATEWAY, BACKUP)
print(f"✓ 备份: {BACKUP}")

# 读取
with open(GATEWAY) as f:
    data = json.load(f)

agents = data.get("agents", {})

print("\n当前 agent 列表:")
for k in sorted(agents.keys()):
    print(f"  {k}")

# 执行 rename
print("\n执行 rename:")
for old, new in RENAME_MAP.items():
    if old in agents:
        agents[new] = agents.pop(old)
        print(f"  {old} → {new}")
    else:
        print(f"  {old}: 不存在，跳过")

# 写回
with open(GATEWAY, "w") as f:
    json.dump(data, f, indent=2)
    f.write("\n")  # 末尾换行

print("\n修改后 agent 列表:")
with open(GATEWAY) as f:
    new_data = json.load(f)
for k in sorted(new_data.get("agents", {}).keys()):
    print(f"  {k}")

print("\n✓ JSON 已更新")
print("请运行以下命令重启 gateway:")
print("  sudo systemctl restart openclaw")
print("  或")
print("  sudo openclaw gateway restart")
