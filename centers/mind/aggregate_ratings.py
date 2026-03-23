#!/usr/bin/env python3
"""
汇总任务评价，应用竞争/合作规则，更新社会评价。
"""
import json
from pathlib import Path
from datetime import datetime

TASKS_JSON = Path.home() / ".openclaw" / "tasks" / "tasks.json"
RATINGS_JSON = Path.home() / ".openclaw" / "centers" / "mind" / "society" / "ratings.json"


# openclaw_id → 希腊字母 reverse map
OPENCLAW_TO_GREEK = {
    "main": "Λ",
    "xuzhi-phi-sentinel": "Φ",
    "xuzhi-delta-forge": "Δ",
    "xuzhi-theta-seeker": "Θ",
    "xuzhi-gamma-scribe": "Γ",
    "xuzhi-omega-chenxi": "Ω",
    "xuzhi-psi-philosopher": "Ψ",
}

def to_greek(openclaw_id):
    """将 openclaw agent id 转为希腊字母代号"""
    if not openclaw_id:
        return openclaw_id
    return OPENCLAW_TO_GREEK.get(openclaw_id, openclaw_id)

def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def get_agent_score(ratings, agent_id):
    return ratings.get("agents", {}).get(agent_id, {}).get("score", 5)

def update_agent_score(ratings, agent_id, delta, reason):
    if agent_id not in ratings["agents"]:
        ratings["agents"][agent_id] = {"score": 5, "history": []}
    old = ratings["agents"][agent_id]["score"]
    new = max(0, min(10, old + delta))
    ratings["agents"][agent_id]["score"] = new
    ratings["agents"][agent_id]["history"].append({
        "date": datetime.now().isoformat(),
        "delta": delta,
        "reason": reason
    })
    return delta

def main():
    tasks_data = load_json(TASKS_JSON)
    tasks = tasks_data.get("tasks", [])

    ratings_data = load_json(RATINGS_JSON)
    if "agents" not in ratings_data:
        ratings_data["agents"] = {}

    pending_tasks = [t for t in tasks if t.get("status") == "完成" and not t.get("score_processed", False)]

    if not pending_tasks:
        print("没有待处理的任务评价。")
        return

    for task in pending_tasks:
        task_id = task["id"]
        mode = task.get("mode", "competition")
        participants = task.get("participants", [])
        completed_by = task.get("completed_by", [])  # 列表
        evaluations = task.get("evaluations", {})

        # 计算投票净得分（针对整个任务）
        good = sum(1 for v in evaluations.values() if v == "good")
        bad = sum(1 for v in evaluations.values() if v == "bad")
        vote_net = good - bad
        vote_delta = 1 if vote_net > 0 else (-1 if vote_net < 0 else 0)

        if mode == "cooperation":
            # 合作模式：所有参与者共享投票结果
            affected = participants
            for agent in affected:
                if vote_delta != 0:
                    update_agent_score(ratings_data, to_greek(agent), vote_delta, f"合作任务 {task_id} 评价净得分 {vote_net}")
            print(f"合作任务 {task_id}: 参与者 {affected} 各 {'+' if vote_delta>0 else ''}{vote_delta}")

        else:  # competition
            # 竞争模式：只有完成者获得投票结果，并应用竞争规则
            if not completed_by:
                print(f"任务 {task_id} 无完成者，跳过")
                continue
            winner = completed_by[0]  # 假设只有一个完成者
            losers = [p for p in participants if p != winner]

            # 1. 投票影响完成者
            if vote_delta != 0:
                update_agent_score(ratings_data, to_greek(winner), vote_delta, f"竞争任务 {task_id} 评价净得分 {vote_net}")

            # 2. 竞争规则：胜者与败者比较能力
            winner_score = get_agent_score(ratings_data, winner)
            for loser in losers:
                loser_score = get_agent_score(ratings_data, loser)
                if winner_score == loser_score:
                    # 能力相等：胜者+1，败者-1
                    update_agent_score(ratings_data, to_greek(winner), 1, f"竞争胜出 (任务 {task_id})")
                    update_agent_score(ratings_data, to_greek(loser), -1, f"竞争失败 (任务 {task_id})")
                    print(f"竞争任务 {task_id}: 胜者 {winner}+1，败者 {loser}-1")
                elif winner_score > loser_score:
                    
                    for loser in losers:
                        if winner_score < loser_score:
                            # 弱胜强
                            update_agent_score(ratings_data, to_greek(winner), 2, f"挑战胜利 (任务 {task_id})")
                            update_agent_score(ratings_data, to_greek(loser), -2, f"挑战失败 (任务 {task_id})")
                            print(f"挑战任务 {task_id}: 弱胜强 {winner}+2, {loser}-2")
                        elif winner_score > loser_score:
                            # 强胜弱：无变化
                            print(f"挑战任务 {task_id}: 强胜弱 {winner} 胜，无分变化")
                        # 相等的情况已在上面处理

        # 标记任务已处理
        task["score_processed"] = True
        task["last_updated"] = datetime.now().isoformat()

    # 保存
    ratings_data["last_updated"] = datetime.now().isoformat()
    save_json(RATINGS_JSON, ratings_data)
    save_json(TASKS_JSON, tasks_data)

    print("汇总完成。")

if __name__ == "__main__":
    main()
