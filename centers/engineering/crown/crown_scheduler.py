#!/usr/bin/env python3
"""
Crown 调度器增强版：根据剩余配额和部门配额生成唤醒队列。
【修改】加入存活检查：仅将评分>0且最近活动时间未超过部门休眠阈值的智能体纳入队列。
"""
import json
import fcntl
from pathlib import Path
from datetime import datetime, timedelta
import random

RATINGS_FILE = Path.home() / ".openclaw" / "centers" / "mind" / "society" / "ratings.json"
DEPARTMENTS_FILE = Path.home() / ".openclaw" / "centers" / "engineering" / "crown" / "departments.json"
QUOTA_FILE = Path.home() / ".openclaw" / "centers" / "engineering" / "crown" / "quota_usage.json"
QUEUE_FILE = Path.home() / ".openclaw" / "centers" / "engineering" / "crown" / "queue.json"

def load_json(path):
    with open(path) as f:
        return json.load(f)

def save_json(path, data):
    with open(path, 'w') as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        json.dump(data, f, indent=2)
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)

def update_json(path, updater):
    """原子读-改-写：持有排他锁直到完整事务完成。updater(data) 修改 data 并返回新 data。"""
    p = Path(path)
    f = open(p, 'r+')
    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
    try:
        data = json.load(f)
        data = updater(data)
        f.seek(0)
        f.truncate()
        json.dump(data, f, indent=2)
    finally:
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        f.close()

def is_alive(agent_info, dept_threshold, now):
    """判断智能体是否存活。
    支持两种ratings格式：
    - 旧格式(灾变前): {score, last_active, department}
    - Xi-era格式: {reliability, quality, notes}
    Xi-era格式：reliability > 0 即视为活跃（无last_active追踪）。
    """
    # Xi-era格式：reliability/quality字段
    if 'reliability' in agent_info or 'quality' in agent_info:
        return agent_info.get('reliability', 0) > 0 or agent_info.get('quality', 0) > 0
    # 旧格式：score + last_active + department
    score = agent_info.get("score", 0)
    if score <= 0:
        return False
    last_active_str = agent_info.get("last_active")
    if not last_active_str:
        return False
    try:
        last_active_str_clean = last_active_str.split('+')[0] if '+' in last_active_str else last_active_str
        last_active = datetime.fromisoformat(last_active_str_clean)
    except:
        return False
    dept = agent_info.get("department", "mind")
    threshold_days = dept_threshold.get(dept, 7)  # 默认7天
    return now - last_active < timedelta(days=threshold_days)

def main():
    ratings = load_json(RATINGS_FILE)
    depts_config = load_json(DEPARTMENTS_FILE)
    quota = load_json(QUOTA_FILE)

    # 提取部门阈值
    dept_threshold = {}
    dept_quota = {}
    if "departments" in depts_config:
        depts = depts_config["departments"]
        for dept_id, info in depts.items():
            dept_threshold[dept_id] = info.get("sleepThreshold", 7)
            dept_quota[dept_id] = info.get("quota_percent", 0)
    else:
        # 兼容直接存放部门配置的情况
        depts = depts_config
        for dept_id, info in depts.items():
            dept_threshold[dept_id] = info.get("sleepThreshold", 7)
            dept_quota[dept_id] = info.get("quota_percent", 0)

    # 支持两种 quota_usage.json 格式：
    # 1. 扁平格式（历史）：{"limit": N, "used": M}
    # 2. 嵌套格式（quota_monitor生成）：{"5_hour": {"quota": N, "used": M, ...}, ...}
    if 'limit' in quota:
        remaining = quota['limit'] - quota['used']
    else:
        tier = quota.get('5_hour', quota.get(list(quota.keys())[0], {}))
        remaining = tier.get('quota', 0) - tier.get('used', 0)
    if remaining > 200:
        wakeups_per_hour = 30
    elif remaining > 100:
        wakeups_per_hour = 20
    elif remaining > 50:
        wakeups_per_hour = 15
    else:
        wakeups_per_hour = 6

    agents = ratings.get("agents", {})
    if not agents:
        print("没有智能体，调度器退出。")
        save_json(QUEUE_FILE, {"queue": [], "generated_at": datetime.now().isoformat(), "total_wakeups": 0, "remaining_quota": remaining})
        return

    now = datetime.now()
    # 按部门收集存活智能体
    dept_agents = {}
    for agent_id, info in agents.items():
        dept = info.get("department", "mind")
        if not is_alive(info, dept_threshold, now):
            continue
        score = info.get("score", 5)
        dept_agents.setdefault(dept, []).append((agent_id, score))

    # 如果没有存活智能体，生成空队列并退出
    if not dept_agents:
        print("没有存活智能体，队列为空。")
        save_json(QUEUE_FILE, {"queue": [], "generated_at": datetime.now().isoformat(), "total_wakeups": 0, "remaining_quota": remaining})
        return

    total_percent = sum(dept_quota.values())
    wakeup_counts = {}
    for dept, percent in dept_quota.items():
        # 如果该部门没有存活智能体，则分配0
        if dept not in dept_agents:
            wakeup_counts[dept] = 0
        else:
            count = round(wakeups_per_hour * percent / total_percent)
            wakeup_counts[dept] = max(count, 1)

    total_assigned = sum(wakeup_counts.values())
    diff = wakeups_per_hour - total_assigned
    # 将差额分配给第一个有存活智能体的部门
    if diff != 0 and dept_agents:
        first_dept = next(iter(dept_agents))
        wakeup_counts[first_dept] += diff

    queue = []
    for dept, count in wakeup_counts.items():
        if dept not in dept_agents or not dept_agents[dept]:
            continue
        # 按评分降序排序
        sorted_agents = sorted(dept_agents[dept], key=lambda x: x[1], reverse=True)
        if count <= len(sorted_agents):
            selected = [a[0] for a in sorted_agents[:count]]
        else:
            selected = []
            for i in range(count):
                selected.append(sorted_agents[i % len(sorted_agents)][0])
        queue.extend(selected)

    random.shuffle(queue)

    queue_data = {
        "queue": queue,
        "generated_at": now.isoformat(),
        "total_wakeups": wakeups_per_hour,
        "remaining_quota": remaining
    }
    save_json(QUEUE_FILE, queue_data)
    print(f"✅ 唤醒队列已生成，剩余配额 {remaining}，每小时唤醒 {wakeups_per_hour} 次，队列长度 {len(queue)}")

if __name__ == "__main__":
    main()
