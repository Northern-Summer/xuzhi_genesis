#!/usr/bin/env python3
"""
认领任务，支持多人参与。
用法: ./claim_task.py <agent_id> [task_id]
如果不指定 task_id，则自动选择一个合适的等待任务。
"""
import json
import sys
from pathlib import Path
from datetime import datetime

TASKS_JSON = Path.home() / ".openclaw" / "tasks" / "tasks.json"
RATINGS_JSON = Path.home() / "xuzhi_genesis" / "centers" / "mind" / "society" / "ratings.json"

def load_json(path):
    with open(path) as f:
        return json.load(f)

def save_json(path, data):
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)

def get_agent_department(agent_id):
    ratings = load_json(RATINGS_JSON)
    return ratings.get("agents", {}).get(agent_id, {}).get("department", "mind")

def main():
    if len(sys.argv) < 2:
        print("用法: claim_task.py <agent_id> [task_id]")
        sys.exit(1)

    agent_id = sys.argv[1]
    specific_task = sys.argv[2] if len(sys.argv) > 2 else None

    tasks_data = load_json(TASKS_JSON)
    tasks = tasks_data.get("tasks", [])

    if specific_task:
        task_id = int(specific_task)
        task = next((t for t in tasks if t["id"] == task_id), None)
        if not task:
            print(f"任务 {task_id} 不存在")
            sys.exit(1)
        if task.get("status") == "等待":
            # 直接认领
            task["status"] = "进行"
            task["participants"] = [agent_id]
            task["participant_times"] = {agent_id: datetime.now().isoformat()}
            print(f"已认领任务 {task_id}")
        elif task.get("status") == "进行":
            # 多人参与
            if agent_id in task.get("participants", []):
                print(f"已在任务 {task_id} 中")
                sys.exit(0)
            task["participants"].append(agent_id)
            if "participant_times" not in task:
                task["participant_times"] = {}
            task["participant_times"][agent_id] = datetime.now().isoformat()
            print(f"已加入任务 {task_id}，当前参与者: {task['participants']}")
        else:
            print(f"任务 {task_id} 状态为 {task.get('status')}，无法认领")
            sys.exit(1)
    else:
        # 自动选择一个等待任务，优先匹配部门
        dept = get_agent_department(agent_id)
        waiting_tasks = [t for t in tasks if t.get("status") == "等待"]
        if not waiting_tasks:
            print("没有等待的任务")
            sys.exit(1)
        dept_match = [t for t in waiting_tasks if t.get("department") == dept]
        if dept_match:
            task = dept_match[0]
        else:
            task = waiting_tasks[0]
        task_id = task["id"]
        task["status"] = "进行"
        task["participants"] = [agent_id]
        task["participant_times"] = {agent_id: datetime.now().isoformat()}
        print(f"已认领任务 {task_id}: {task.get('title')}")

    tasks_data["last_updated"] = datetime.now().isoformat()
    save_json(TASKS_JSON, tasks_data)

if __name__ == "__main__":
    main()
