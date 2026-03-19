#!/usr/bin/env python3
"""
共识检测器：扫描已完成任务，统计种子引用次数，生成元种子。
"""
import json
import shutil
from pathlib import Path
from datetime import datetime
import sys

TASKS_JSON = Path.home() / ".openclaw" / "tasks" / "tasks.json"
META_SEEDS_DIR = Path.home() / "xuzhi_genesis" / "centers" / "intelligence" / "seeds" / "meta"
CONSENSUS_THRESHOLD = 3  # 触发共识的引用次数

def load_json(path):
    with open(path) as f:
        return json.load(f)

def save_json(path, data):
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)

def generate_meta_seed(seed_name, agents, tasks):
    """生成元种子文件"""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    filename = f"meta_{timestamp}.md"
    filepath = META_SEEDS_DIR / filename
    content = f"""# 元种子 - 共识发现

生成时间: {datetime.now().isoformat()}

## 共识种子
- 种子名称: {seed_name}

## 共识达成者
{chr(10).join('- ' + a for a in agents)}

## 相关任务
{chr(10).join('- 任务 ' + str(t) for t in tasks)}

## 置信度
基于 {len(agents)} 个独立智能体的引用，共识置信度高。
"""
    with open(filepath, 'w') as f:
        f.write(content)
    print(f"✅ 生成元种子: {filepath}")
    return filepath

def main():
    if not TASKS_JSON.exists():
        print("任务文件不存在")
        return

    data = load_json(TASKS_JSON)
    tasks = data.get("tasks", [])

    # 统计每个种子被哪些智能体在哪些任务中引用
    seed_refs = {}
    for t in tasks:
        if t.get("status") != "完成":
            continue
        agents = t.get("completed_by", [])
        if not agents:
            continue
        seeds = t.get("referenced_seeds", [])
        for s in seeds:
            if s not in seed_refs:
                seed_refs[s] = {"agents": set(), "tasks": set()}
            seed_refs[s]["agents"].update(agents)
            seed_refs[s]["tasks"].add(t["id"])

    # 检查哪些种子达到共识阈值
    for seed, info in seed_refs.items():
        agent_count = len(info["agents"])
        if agent_count >= CONSENSUS_THRESHOLD:
            # 检查是否已存在此种子的元种子（防止重复生成）
            existing = list(META_SEEDS_DIR.glob(f"*{seed}*"))  # 简单判断
            if existing:
                print(f"种子 {seed} 的元种子已存在，跳过")
                continue
            generate_meta_seed(seed, list(info["agents"]), list(info["tasks"]))

if __name__ == "__main__":
    main()
