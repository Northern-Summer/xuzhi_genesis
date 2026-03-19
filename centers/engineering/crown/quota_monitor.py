#!/usr/bin/env python3
"""
配额监控与动态cron调整 - 增强版
新增：生成部门配额分配文件（每小时、每日）
"""
import json
import os
import sys
import requests
from pathlib import Path
from datetime import datetime

# 配置文件路径
SECRETS_FILE = Path.home() / ".openclaw" / "secrets.json"
QUOTA_FILE = Path.home() / ".openclaw" / "centers" / "engineering" / "crown" / "quota_usage.json"
CRON_FILE = Path.home() / ".openclaw" / "cron" / "dynamic_crontab.txt"
API_URL = "https://cloud.infini-ai.com/maas/coding/usage"  # 确保与curl一致

# 新增：部门配额输出文件
DEPT_HOURLY_FILE = Path.home() / ".openclaw" / "centers" / "engineering" / "crown" / "quota_department_hourly.json"
DEPT_DAILY_FILE = Path.home() / ".openclaw" / "centers" / "engineering" / "crown" / "quota_department_daily.json"
DEPARTMENTS_FILE = Path.home() / ".openclaw" / "centers" / "engineering" / "crown" / "departments.json"

def get_api_key():
    """从secrets.json或环境变量获取API密钥"""
    # 优先从secrets.json读取
    if SECRETS_FILE.exists():
        try:
            with open(SECRETS_FILE) as f:
                secrets = json.load(f)
            api_key = secrets.get("accelerator_api_key")
            if api_key:
                return api_key.strip()  # 去除可能的多余空白
        except Exception as e:
            print(f"⚠️ 读取secrets.json失败: {e}")
    # 其次从环境变量读取
    api_key = os.environ.get("ACCELERATOR_API_KEY")
    if api_key:
        return api_key.strip()
    api_key = os.environ.get("INFINI_API_KEY")
    if api_key:
        return api_key.strip()
    return None

def fetch_quota_from_api():
    """调用加速器API获取配额使用情况（精确对齐curl）"""
    api_key = get_api_key()
    if not api_key:
        print("❌ 未找到API密钥，请在secrets.json中设置 accelerator_api_key 或设置环境变量 ACCELERATOR_API_KEY")
        return None

    headers = {
        "Authorization": f"Bearer {api_key}",
        "User-Agent": "curl/7.68.0"  # 模拟curl的User-Agent，避免被拒绝
    }
    try:
        print(f"🔍 正在请求API: {API_URL}")
        resp = requests.get(API_URL, headers=headers, timeout=15)
        print(f"📡 响应状态码: {resp.status_code}")
        print(f"📄 响应头: {dict(resp.headers)}")
        print(f"📦 响应内容预览: {resp.text[:200]}")

        resp.raise_for_status()
        data = resp.json()

        # 提取30天配额（与curl返回的结构一致）
        quota_info = data.get("30_day", {})
        limit = quota_info.get("quota", 0)
        used = quota_info.get("used", 0)
        remain = quota_info.get("remain", limit - used)

        result = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "used": used,
            "limit": limit,
            "remain": remain,
            "last_update": datetime.now().isoformat()
        }
        print(f"✅ 解析到的配额: {result}")
        return result
    except requests.exceptions.RequestException as e:
        print(f"❌ 网络请求异常: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"   响应状态码: {e.response.status_code}")
            print(f"   响应内容: {e.response.text[:200]}")
    except json.JSONDecodeError as e:
        print(f"❌ JSON解析失败: {e}")
    except Exception as e:
        print(f"❌ 未知错误: {e}")
    return None

def save_quota(quota):
    """保存配额到本地文件"""
    QUOTA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(QUOTA_FILE, 'w') as f:
        json.dump(quota, f, indent=2)

def load_quota():
    """加载配额：优先从API获取，失败则回退到本地文件"""
    quota = fetch_quota_from_api()
    if quota:
        save_quota(quota)
        return quota
    if QUOTA_FILE.exists():
        with open(QUOTA_FILE) as f:
            return json.load(f)
    # 完全失败，返回默认保守值
    return {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "used": 0,
        "limit": 400,
        "remain": 400,
        "last_update": datetime.now().isoformat()
    }

def get_wakeups_per_hour(remaining):
    """根据剩余配额计算每小时唤醒次数（激进版）"""
    if remaining > 200:
        return 30
    elif remaining > 100:
        return 20
    elif remaining > 50:
        return 10
    else:
        return 6

def generate_department_allocation(quota):
    """生成部门配额分配文件（每小时和每日）"""
    if not DEPARTMENTS_FILE.exists():
        print("⚠️ departments.json 不存在，无法生成部门分配")
        return

    with open(DEPARTMENTS_FILE) as f:
        depts_data = json.load(f)

    # 提取部门百分比
    dept_percent = {}
    if "departments" in depts_data:
        depts = depts_data["departments"]
        for dept_id, info in depts.items():
            dept_percent[dept_id] = info.get("quota_percent", 0)
    else:
        depts = depts_data
        for dept_id, info in depts.items():
            dept_percent[dept_id] = info.get("quota_percent", 0)

    total_percent = sum(dept_percent.values())
    if total_percent == 0:
        print("⚠️ 部门百分比总和为0，无法分配")
        return

    # 每日总配额（限90%可用，10%机动）
    daily_total = quota['limit'] * 0.9
    daily_remain = quota['remain'] * 0.9  # 剩余配额也按90%分配

    # 计算各部门每日配额（四舍五入）
    daily_allocation = {}
    for dept, percent in dept_percent.items():
        daily_allocation[dept] = round(daily_remain * percent / total_percent)

    # 每小时唤醒次数（基于剩余比例）
    remaining = quota['remain']
    wakeups_per_hour = get_wakeups_per_hour(remaining)

    # 计算各部门每小时可唤醒次数
    hourly_allocation = {}
    for dept, percent in dept_percent.items():
        # 每小时唤醒次数按百分比分配，四舍五入，至少1次（如果部门存在）
        count = round(wakeups_per_hour * percent / total_percent)
        if count < 1:
            count = 1
        hourly_allocation[dept] = count

    # 保存到文件
    DEPT_HOURLY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(DEPT_HOURLY_FILE, 'w') as f:
        json.dump({
            "date": quota['date'],
            "total_hourly_wakeups": wakeups_per_hour,
            "hourly_allocation": hourly_allocation,
            "remaining_quota": remaining,
            "last_update": quota['last_update']
        }, f, indent=2)

    with open(DEPT_DAILY_FILE, 'w') as f:
        json.dump({
            "date": quota['date'],
            "daily_total": daily_total,
            "daily_allocation": daily_allocation,
            "remaining_quota": remaining,
            "last_update": quota['last_update']
        }, f, indent=2)

    print(f"✅ 部门配额已生成：每小时={hourly_allocation}，每日={daily_allocation}")

def adjust_cron(quota):
    """根据剩余配额调整cron间隔"""
    remaining = quota.get('remain', quota['limit'] - quota['used'])
    total = quota['limit']
    # 剩余比例映射到间隔 10~60 分钟
    ratio = remaining / total if total > 0 else 0.5
    interval = int(10 + (1 - ratio) * 50)
    interval = max(10, min(60, interval))

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
    CRON_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CRON_FILE, 'w') as f:
        f.write(cron_content)
    os.system(f"crontab {CRON_FILE}")
    print(f"[{datetime.now()}] 动态cron已更新：间隔={interval}分钟，剩余={remaining}")

def main():
    quota = load_quota()
    adjust_cron(quota)
    generate_department_allocation(quota)

if __name__ == "__main__":
    main()
