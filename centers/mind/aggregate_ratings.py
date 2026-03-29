#!/usr/bin/env python3
# 工程改进铁律合规 — Ξ | 2026-03-29
# 自问：此操作是否让系统更安全/准确/优雅/高效？答案：YES
"""
汇总任务评价，应用竞争/合作规则，更新社会评价。
"""
import json
from pathlib import Path
from datetime import datetime

TASKS_JSON = Path.home() / ".openclaw" / "tasks" / "tasks.json"
RATINGS_JSON = Path.home() / ".openclaw" / "centers" / "mind" / "society" / "ratings.json"
LOG_FILE = Path.home() / ".openclaw" / "logs" / "aggregate_ratings.log"

OPENCLAW_TO_GREEK = {
    "main": "Ξ",
    "xuzhi-phi-sentinel": "Φ",
    "xuzhi-delta-forge": "Δ",
    "xuzhi-theta-seeker": "Θ",
    "xuzhi-gamma-scribe": "Γ",
    "xuzhi-omega-chenxi": "Ω",
    "xuzhi-psi-philosopher": "Ψ",
}

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

def to_greek(oid):
    return OPENCLAW_TO_GREEK.get(oid, oid)

def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))

def save_json(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    log(f"已保存 {path.name}")

def update_score(ratings, aid, delta, reason):
    if aid not in ratings["agents"]:
        ratings["agents"][aid] = {"score": 5, "history": []}
    old = ratings["agents"][aid]["score"]
    new = max(0, min(10, old + delta))
    ratings["agents"][aid]["score"] = new
    ratings["agents"][aid]["history"].append({"date": datetime.now().isoformat(), "delta": delta, "reason": reason})
    return delta

def main():
    log("启动")
    tasks_data = load_json(TASKS_JSON)
    tasks = tasks_data if isinstance(tasks_data, list) else tasks_data.get("tasks", [])
    ratings = load_json(RATINGS_JSON)
    ratings.setdefault("agents", {})

    pending = [t for t in tasks if t.get("status") == "完成" and not t.get("score_processed", False)]
    if not pending:
        log("无待处理任务")
        return

    for task in pending:
        evaluations = task.get("evaluations", {})
        good = sum(1 for v in evaluations.values() if v == "good")
        bad = sum(1 for v in evaluations.values() if v == "bad")
        net = good - bad
        delta = 1 if net > 0 else (-1 if net < 0 else 0)
        participants = task.get("participants", [])
        completed = task.get("completed_by", [])
        winner = completed[0] if completed else None

        if task.get("mode") == "cooperation":
            for a in participants:
                if delta:
                    update_score(ratings, to_greek(a), delta, f"合作 {task['id']}")
            log(f"合作任务 {task['id']}: {delta}")
        else:
            if winner and delta:
                update_score(ratings, to_greek(winner), delta, f"竞争投票 {task['id']}")
            if winner:
                ws = ratings["agents"].get(to_greek(winner), {}).get("score", 5)
                for p in participants:
                    if p == winner:
                        continue
                    ps = ratings["agents"].get(to_greek(p), {}).get("score", 5)
                    if ws == ps:
                        update_score(ratings, to_greek(winner), 1, f"竞争胜出 {task['id']}")
                        update_score(ratings, to_greek(p), -1, f"竞争失败 {task['id']}")
                    elif ws > ps:
                        pass
                    else:
                        update_score(ratings, to_greek(winner), 2, f"挑战胜利 {task['id']}")
                        update_score(ratings, to_greek(p), -2, f"挑战失败 {task['id']}")
        task["score_processed"] = True
        task["last_updated"] = datetime.now().isoformat()

    ratings["last_updated"] = datetime.now().isoformat()
    save_json(RATINGS_JSON, ratings)
    save_json(TASKS_JSON, tasks)
    log("完成")

if __name__ == "__main__":
    main()
