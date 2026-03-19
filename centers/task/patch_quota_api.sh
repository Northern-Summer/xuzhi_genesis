#!/usr/bin/env bash
# 补丁：修改 quota_monitor.py 使用加速器API获取配额
set -euo pipefail

TARGET="/home/summer/xuzhi_genesis/centers/engineering/crown/quota_monitor.py"
BACKUP="${TARGET}.bak.$(date +%Y%m%d-%H%M%S)"

# 备份
cp "$TARGET" "$BACKUP"
echo "✅ 已备份原文件到 $BACKUP"

# 新文件内容
cat > "$TARGET" << 'EOF'
#!/usr/bin/env python3
"""
配额监控与动态cron调整
直接从加速器API获取实时配额，不再依赖本地记录。
"""
import json
import os
import sys
import requests
from pathlib import Path
from datetime import datetime

# 配置文件路径（用于存储API密钥）
SECRETS_FILE = Path.home() / ".openclaw" / "secrets.json"
# 配额文件（可选，用于记录或回退）
QUOTA_FILE = Path.home() / ".openclaw" / "centers" / "engineering" / "crown" / "quota_usage.json"
CRON_FILE = Path.home() / ".openclaw" / "cron" / "dynamic_crontab.txt"

# 加速器API地址
API_URL = "https://cloud.infini-ai.com/maas/coding/usage"

def get_api_key():
    """从secrets.json或环境变量获取API密钥"""
    # 优先从secrets.json读取
    if SECRETS_FILE.exists():
        with open(SECRETS_FILE) as f:
            secrets = json.load(f)
        api_key = secrets.get("accelerator_api_key")
        if api_key:
            return api_key
    # 其次从环境变量读取
    api_key = os.environ.get("ACCELERATOR_API_KEY")
    if api_key:
        return api_key
    # 如果都没有，尝试从环境变量读取旧的变量名（兼容）
    api_key = os.environ.get("INFINI_API_KEY")
    if api_key:
        return api_key
    return None

def fetch_quota_from_api():
    """调用加速器API获取配额使用情况"""
    api_key = get_api_key()
    if not api_key:
        print("❌ 未找到API密钥，请在secrets.json中设置 accelerator_api_key 或设置环境变量 ACCELERATOR_API_KEY")
        return None
    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        resp = requests.get(API_URL, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        # 提取30天配额和已用量
        quota_info = data.get("30_day", {})
        limit = quota_info.get("quota", 0)
        used = quota_info.get("used", 0)
        remain = quota_info.get("remain", limit - used)
        return {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "used": used,
            "limit": limit,
            "remain": remain,
            "last_update": datetime.now().isoformat()
        }
    except Exception as e:
        print(f"❌ 从API获取配额失败: {e}")
        return None

def load_quota():
    """加载配额（优先从API，失败则回退到本地文件）"""
    quota = fetch_quota_from_api()
    if quota:
        # 同时保存到本地文件作为备份
        save_quota(quota)
        return quota
    # API失败，尝试从本地文件读取
    if QUOTA_FILE.exists():
        with open(QUOTA_FILE) as f:
            return json.load(f)
    else:
        # 完全失败，返回默认值（但cron会保守运行）
        return {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "used": 0,
            "limit": 400,
            "remain": 400,
            "last_update": datetime.now().isoformat()
        }

def save_quota(quota):
    """将配额保存到本地文件（备份）"""
    QUOTA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(QUOTA_FILE, 'w') as f:
        json.dump(quota, f, indent=2)

def adjust_cron(quota):
    """根据剩余配额动态调整cron间隔"""
    remaining = quota.get('remain', quota['limit'] - quota['used'])
    total = quota['limit']

    # 计算间隔：剩余越多，间隔越小（越频繁）
    # 剩余比例 -> 映射到 10~60 分钟
    ratio = remaining / total if total > 0 else 0.5
    interval = int(10 + (1 - ratio) * 50)  # 剩余100% -> 10分钟，剩余0% -> 60分钟
    interval = max(10, min(60, interval))

    # 生成crontab内容（保留原有基础任务）
    cron_content = f"""# 动态crontab，由quota_monitor.py自动生成
# 心跳任务（根据剩余配额调整间隔）
*/{interval} * * * * $HOME/.openclaw/workspace/sense_hardware.sh
*/10 * * * * $HOME/.openclaw/workspace/pulse_aggressive.sh

# 每日心智种子（固定凌晨3点）
0 3 * * * $HOME/.openclaw/centers/intelligence/seeds/daily_mind_seeds_v2.py

# 记忆压缩（每小时）
0 * * * * $HOME/.openclaw/centers/engineering/memory_forge.py

# 社会评价汇总（每小时）
0 * * * * $HOME/.openclaw/centers/mind/aggregate_ratings.py

# 排行榜更新（每小时过5分）
5 * * * * $HOME/.openclaw/centers/mind/society/update_leaderboard.py

# 配额监控自身（每30分钟）
*/30 * * * * $HOME/.openclaw/centers/engineering/crown/quota_monitor.py
"""
    # 写入临时文件并加载到cron
    CRON_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CRON_FILE, 'w') as f:
        f.write(cron_content)
    os.system(f"crontab {CRON_FILE}")
    print(f"[{datetime.now()}] 动态cron已更新：间隔={interval}分钟，剩余={remaining}")

def main():
    quota = load_quota()
    adjust_cron(quota)

if __name__ == "__main__":
    main()
EOF

echo "✅ 已更新 $TARGET"
echo "⚠️ 请确保你的API密钥已配置："
echo "   - 在 ~/.openclaw/secrets.json 中添加: {\"accelerator_api_key\": \"sk-cp-xxxxx\"}"
echo "   或"
echo "   - 设置环境变量: export ACCELERATOR_API_KEY=sk-cp-xxxxx"
echo ""
echo "📌 现在 quota_monitor.py 将直接从加速器API获取实时配额，并根据剩余配额动态调整cron任务间隔。"
