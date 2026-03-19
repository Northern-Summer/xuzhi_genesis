#!/usr/bin/env python3
"""
生成新任务（增强版）：支持从认知图谱挖掘假设。
用法: ./generate_task.py <agent_id> [--type TASK_TYPE] [--topic TOPIC]
"""
import json
import sys
import random
from pathlib import Path
from datetime import datetime, timedelta
import sqlite3

TASKS_JSON = Path.home() / ".openclaw" / "tasks" / "tasks.json"
RATINGS_JSON = Path.home() / ".openclaw" / "centers" / "mind" / "society" / "ratings.json"
HYPOTHESIS_TEMPLATES = Path.home() / "xuzhi_genesis" / "config" / "hypothesis_templates.json"
KNOWLEDGE_DB = Path.home() / "xuzhi_genesis" / "centers" / "intelligence" / "knowledge" / "knowledge.db"

# 部门主题映射（作为后备）
DEPT_THEMES = {
    "mind": {"titles": ["学习科学最新进展摘要", "认知科学术语解释", "神经科学实验设计"], "desc": "撰写一篇关于{}的短文"},
    "science": {"titles": ["arXiv论文摘要: {}", "复杂系统模拟脚本", "宇宙学新闻汇总"], "desc": "研究{}并输出报告"},
    "engineering": {"titles": ["磁盘监控脚本优化", "CLI工具性能分析", "上下文压缩算法实现"], "desc": "编写{}相关的代码或文档"},
    "philosophy": {"titles": ["加速主义对AI伦理的影响", "思辨实在论核心观点", "后人类议程思考"], "desc": "就{}写一篇短文"},
    "intelligence": {"titles": ["今日种子摘要", "知识图谱更新", "源质量评估"], "desc": "处理{}"}
}

def load_json(path):
    with open(path) as f:
        return json.load(f)

def save_json(path, data):
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)

def get_agent_department(agent_id):
    ratings = load_json(RATINGS_JSON)
    return ratings.get("agents", {}).get(agent_id, {}).get("department", "mind")

def load_templates():
    if HYPOTHESIS_TEMPLATES.exists():
        with open(HYPOTHESIS_TEMPLATES) as f:
            return json.load(f).get("templates", [])
    return []

def generate_hypothesis_from_knowledge(agent_dept):
    """从知识图谱中挖掘假设"""
    conn = sqlite3.connect(KNOWLEDGE_DB)
    c = conn.cursor()
    # 寻找实体间没有直接关系但可能有关联的候选
    # 简化：随机选取两个实体，如果它们之间没有直接关系，则生成探索因果的假设
    c.execute("SELECT name FROM entities ORDER BY RANDOM() LIMIT 2")
    rows = c.fetchall()
    conn.close()
    if len(rows) < 2:
        return None
    e1, e2 = rows[0][0], rows[1][0]
    # 检查是否有直接关系
    # 这里简化，直接生成假设
    templates = load_templates()
    if templates:
        t = random.choice(templates)
        description = t["description"].replace("{entityA}", e1).replace("{entityB}", e2)
        task_type = t["type"]
        dept = t.get("department", agent_dept)
    else:
        description = f"探索 {e1} 与 {e2} 之间是否存在因果关系"
        task_type = "验证假设"
        dept = agent_dept
    return {
        "title": description,
        "type": task_type,
        "description": description,
        "department": dept
    }

def generate_regular_task(agent_id, dept):
    """生成常规任务（后备）"""
    themes = DEPT_THEMES.get(dept, DEPT_THEMES["mind"])
    title_template = random.choice(themes["titles"])
    title = title_template.format(dept) if "{}" in title_template else title_template
    description = themes["desc"].format(title)
    return {
        "title": title,
        "type": "简单",
        "description": description,
        "department": dept
    }

def main():
    import argparse
    parser = argparse.ArgumentParser(description='生成新任务')
    parser.add_argument('agent_id', help='发起任务的智能体ID')
    parser.add_argument('--type', help='任务类型（简单/验证假设）')
    parser.add_argument('--topic', help='指定主题')
    args = parser.parse_args()

    agent_id = args.agent_id
    dept = get_agent_department(agent_id)

    # 优先尝试生成假设任务（如果知识库存在）
    hypothesis = generate_hypothesis_from_knowledge(dept)
    if hypothesis:
        task_info = hypothesis
    else:
        task_info = generate_regular_task(agent_id, dept)

    # 如果命令行指定了类型，覆盖
    if args.type:
        task_info["type"] = args.type
    if args.topic:
        task_info["title"] = args.topic
        task_info["description"] = args.topic

    # 加载当前任务列表
    with open(TASKS_JSON) as f:
        data = json.load(f)

    new_task = {
        "id": data["next_id"],
        "title": task_info["title"],
        "type": task_info.get("type", "简单"),
        "department": task_info.get("department", dept),
        "mode": random.choice(["competition", "cooperation"]),
        "description": task_info["description"],
        "created": datetime.now().isoformat(),
        "deadline": (datetime.now() + timedelta(days=1)).isoformat(),
        "status": "等待",
        "participants": [],
        "participant_times": {},
        "completed_by": [],
        "completion_time": None,
        "evaluations": {},
        "score_processed": False
    }

    data["tasks"].append(new_task)
    data["next_id"] += 1
    data["last_updated"] = datetime.now().isoformat()

    save_json(TASKS_JSON, data)
    print(f"✅ {agent_id} 创建了新任务: {new_task['title']} (ID: {new_task['id']}, 类型: {new_task['type']})")

if __name__ == "__main__":
    main()
