#!/usr/bin/env python3
"""
死亡检测：扫描评分≤0的智能体，以及超过休眠阈值未活动的智能体。
放置于心智中心。
"""
import json
import shutil
from pathlib import Path
from datetime import datetime, timedelta

XUZHI_HOME = Path.home() / 'xuzhi_genesis'
RATINGS_JSON = XUZHI_HOME / 'centers' / 'mind' / 'society' / 'ratings.json'
DEPARTMENTS_JSON = Path.home() / 'xuzhi_genesis' / 'centers' / 'engineering' / 'crown' / 'departments.json'
AGENTS_DIR = Path.home() / '.openclaw' / 'agents'
ARCHIVE_DIR = Path.home() / '.openclaw' / 'archive' / 'agents'
BROADCAST_FILE = Path.home() / '.openclaw' / 'workspace' / 'broadcast.md'

ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

def load_json(path):
    with open(path) as f:
        return json.load(f)

def save_json(path, data):
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)

def get_department_threshold(dept):
    """从 departments.json 获取部门休眠阈值，默认 7 天"""
    try:
        with open(DEPARTMENTS_JSON) as f:
            depts = json.load(f)
        return depts.get('departments', {}).get(dept, {}).get('sleepThreshold', 7)
    except:
        return 7

def main():
    if not RATINGS_JSON.exists():
        print("ratings.json 不存在，退出")
        return

    data = load_json(RATINGS_JSON)
    agents = data.get('agents', {})
    now = datetime.now()
    dead_agents = []
    sleep_agents = []

    for agent_id, props in agents.items():
        # 1. 分数≤0 直接死亡
        if props.get('score', 0) <= 0:
            dead_agents.append(agent_id)
            continue

        # 2. 检查最后活动时间
        last_active_str = props.get('last_active')
        if not last_active_str:
            # 如果没有记录，视为刚刚活跃，跳过（避免误杀）
            continue

        try:
            last_active = datetime.fromisoformat(last_active_str)
        except:
            continue

        dept = props.get('department', 'mind')
        threshold = get_department_threshold(dept)
        days_inactive = (now - last_active).days

        if days_inactive > threshold + 1:
            dead_agents.append(agent_id)
        elif threshold < days_inactive <= threshold + 1:
            # 标记为休眠
            props['status'] = 'sleep'
            sleep_agents.append(agent_id)

    if dead_agents:
        print(f"发现死亡智能体: {dead_agents}")
        # 备份 ratings.json
        backup = RATINGS_JSON.with_suffix('.json.bak')
        shutil.copy2(RATINGS_JSON, backup)
        print(f"已备份 -> {backup}")

        for agent_id in dead_agents:
            # 归档私有领地
            src = AGENTS_DIR / agent_id
            if src.exists():
                dst = ARCHIVE_DIR / f"{agent_id}.{datetime.now().strftime('%Y%m%d%H%M%S')}"
                print(f"归档 {src} -> {dst}")
                shutil.move(str(src), str(dst))
            else:
                print(f"警告: 智能体目录 {src} 不存在")
            # 从评价中移除
            del agents[agent_id]

        # 触发悼亡广播
        if BROADCAST_FILE.exists():
            with open(BROADCAST_FILE, 'a') as f:
                f.write(f"\n[心智中心] 悼亡: 智能体 {', '.join(dead_agents)} 已死亡，归档完毕。\n")

    if sleep_agents:
        print(f"发现休眠智能体: {sleep_agents}")
        if BROADCAST_FILE.exists():
            with open(BROADCAST_FILE, 'a') as f:
                f.write(f"\n[心智中心] 休眠: 智能体 {', '.join(sleep_agents)} 已进入休眠状态。\n")

    # 保存更新（包括休眠标记）
    save_json(RATINGS_JSON, data)

    if not dead_agents and not sleep_agents:
        print("未发现评分≤0或需休眠的智能体")

if __name__ == '__main__':
    main()
