#!/bin/bash
# 唤醒指定智能体：先尝试认领任务，若无任务则尝试评价已完成任务，若无评价且等待任务少则生成新任务
AGENT=$1
LOG_FILE="$HOME/.openclaw/logs/wakeup.log"
TASKS_JSON="$HOME/.openclaw/tasks/tasks.json"
VOTE_SCRIPT="$HOME/xuzhi_genesis/centers/mind/vote_on_task.py"
GENERATE_SCRIPT="$HOME/xuzhi_genesis/centers/task/generate_task.py"

echo "[$(date)] 唤醒 $AGENT" >> "$LOG_FILE"

python3 << EOF2
import json
from pathlib import Path
from datetime import datetime
import subprocess
import sys

agent = "$AGENT"
tasks_file = Path("$TASKS_JSON")
vote_script = Path("$VOTE_SCRIPT")
generate_script = Path("$GENERATE_SCRIPT")

# ----- 新增：更新 last_active 函数 -----
def update_last_active(agent_id):
    ratings_file = Path.home() / ".openclaw" / "centers" / "mind" / "society" / "ratings.json"
    if not ratings_file.exists():
        return
    with open(ratings_file) as f:
        ratings = json.load(f)
    agents = ratings.get("agents", {})
    if agent_id in agents:
        agents[agent_id]["last_active"] = datetime.now().isoformat()
        with open(ratings_file, 'w') as f:
            json.dump(ratings, f, indent=2)
# --------------------------------------

if not tasks_file.exists():
    print(f"任务文件不存在: {tasks_file}")
    update_last_active(agent)
    sys.exit(1)

with open(tasks_file) as f:
    data = json.load(f)

# ===== 1. 先尝试认领一个等待的任务 =====
pending_tasks = [t for t in data.get('tasks', []) if t.get('status') == '等待']
if pending_tasks:
    # 优先选择与智能体部门匹配的任务
    # 获取智能体的部门（从 ratings.json 读取）
    ratings_file = Path.home() / ".openclaw" / "centers" / "mind" / "society" / "ratings.json"
    with open(ratings_file) as rf:
        ratings = json.load(rf)
    agent_info = ratings.get("agents", {}).get(agent, {})
    dept = agent_info.get("department", "mind")
    dept_match = [t for t in pending_tasks if t.get('department') == dept]
    if dept_match:
        task = dept_match[0]
    else:
        task = pending_tasks[0]
    task_id = task['id']

    # 认领任务
    for t in data['tasks']:
        if t['id'] == task_id:
            t['status'] = '进行'
            t['claimed_by'] = agent
            t['claimed_time'] = datetime.now().isoformat()
            break

    with open(tasks_file, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"[{agent}] 已认领任务 {task_id}: {task.get('title')}")
    update_last_active(agent)
    sys.exit(0)

# ===== 2. 如果没有等待任务，则尝试评价一个已完成但未计入的任务 =====
completed_tasks = [t for t in data.get('tasks', []) if t.get('status') == '完成' and not t.get('score_processed', False)]

if completed_tasks:
    # 按任务 ID 升序选择最早的任务（ID 越小越早创建）
    completed_tasks.sort(key=lambda t: t['id'])
    task = completed_tasks[0]
    task_id = task['id']

    # 获取当前智能体的评分
    ratings_file = Path.home() / ".openclaw" / "centers" / "mind" / "society" / "ratings.json"
    with open(ratings_file) as rf:
        ratings = json.load(rf)
    current_score = ratings.get("agents", {}).get(agent, {}).get("score", 5)

    # 获取任务完成者的平均评分
    completed_by = task.get('completed_by', [])
    if completed_by:
        scores = [ratings.get("agents", {}).get(c, {}).get("score", 5) for c in completed_by]
        avg_score = sum(scores) / len(scores)
        vote = 'good' if avg_score >= current_score else 'bad'
    else:
        vote = 'good'

    subprocess.run([str(vote_script), str(task_id), agent, vote])
    print(f"[{agent}] 对任务 {task_id} 投票: {vote}")
    update_last_active(agent)
    sys.exit(0)

# ===== 3. 如果既无任务也无评价，且等待任务太少，则生成新任务 =====
pending_count = len([t for t in data.get('tasks', []) if t.get('status') == '等待'])
if pending_count < 3:
    subprocess.run([sys.executable, str(generate_script), agent])
else:
    print(f"[{agent}] 暂无待处理任务和待评价任务")
update_last_active(agent)
EOF2
