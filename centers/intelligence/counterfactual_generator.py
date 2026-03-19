#!/usr/bin/env python3
"""
因果反事实推演生成器：基于知识图谱中的因果关系，生成反事实问题。
"""
import json
import sqlite3
import random
import requests
import sys
from pathlib import Path
from datetime import datetime, timedelta

KNOWLEDGE_DB = Path.home() / "xuzhi_genesis" / "centers" / "intelligence" / "knowledge" / "knowledge.db"
TASKS_JSON = Path.home() / ".openclaw" / "tasks" / "tasks.json"
LOG_FILE = Path.home() / "xuzhi_genesis" / "logs" / "counterfactual.log"
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen3.5:4b"

def log(msg):
    with open(LOG_FILE, 'a') as f:
        f.write(f"[{datetime.now().isoformat()}] {msg}\n")

def load_json(path):
    with open(path) as f:
        return json.load(f)

def save_json(path, data):
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)

def get_causal_edges():
    """从知识图谱中获取所有因果关系边（predicate 包含因果关键词）"""
    conn = sqlite3.connect(KNOWLEDGE_DB)
    c = conn.cursor()
    c.execute('''
        SELECT e1.name, e2.name, r.predicate, r.confidence
        FROM relations r
        JOIN entities e1 ON r.subject_id = e1.id
        JOIN entities e2 ON r.object_id = e2.id
        WHERE r.predicate IN ('causes', 'leads to', 'increases', 'decreases', 'prevents')
    ''')
    edges = c.fetchall()
    conn.close()
    return edges

def generate_counterfactual_question(cause, effect, predicate, confidence):
    """调用本地模型生成反事实问题"""
    prompt = f"""基于以下因果关系：
{cause} {predicate} {effect}（置信度 {confidence:.2f}）

请生成一个反事实问题，探索如果 {cause} 没有发生（或相反情况），那么 {effect} 会怎样？
问题应当具体、可验证，以“如果……会怎样？”的格式。
只输出问题本身。"""
    try:
        resp = requests.post(OLLAMA_URL, json={
            "model": MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.8, "max_tokens": 100}
        }, timeout=30)
        resp.raise_for_status()
        result = resp.json()
        return result.get("response", "").strip()
    except Exception as e:
        log(f"模型调用失败: {e}")
        return None

def create_counterfactual_task(question, cause, effect):
    with open(TASKS_JSON) as f:
        data = json.load(f)

    new_task = {
        "id": data["next_id"],
        "title": question,
        "type": "验证假设",
        "subtype": "causal_counterfactual",
        "department": "science",
        "mode": "competition",
        "description": question,
        "hypothesis": {
            "cause": cause,
            "effect": effect,
            "counterfactual": True
        },
        "created": datetime.now().isoformat(),
        "deadline": (datetime.now() + timedelta(days=2)).isoformat(),
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
    return new_task["id"]

def main():
    log("开始因果反事实生成")
    edges = get_causal_edges()
    if not edges:
        log("无因果关系边，跳过")
        return

    # 随机选择一条边
    cause, effect, pred, conf = random.choice(edges)
    question = generate_counterfactual_question(cause, effect, pred, conf)
    if not question:
        return

    task_id = create_counterfactual_task(question, cause, effect)
    log(f"生成因果反事实任务 ID {task_id}: {question}")

if __name__ == "__main__":
    main()
