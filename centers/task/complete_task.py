#!/usr/bin/env python3
"""
标记任务为完成，支持引用种子和验证假设。
用法: ./complete_task.py <task_id> <agent_id> [--model MODEL] [--calls CALLS] [--seeds SEED1 ...] [--confirm yes/no]
"""
import argparse
import json
import sys
from pathlib import Path
from datetime import datetime

TASKS_JSON = Path.home() / ".openclaw" / "tasks" / "tasks.json"
KNOWLEDGE_DB = Path.home() / "xuzhi_genesis" / "centers" / "intelligence" / "knowledge" / "knowledge.db"

def update_hypothesis_confidence(entity1, entity2, confirmed):
    """根据验证结果更新知识库中关系的置信度"""
    import sqlite3
    conn = sqlite3.connect(KNOWLEDGE_DB)
    c = conn.cursor()
    # 查找实体ID
    c.execute("SELECT id FROM entities WHERE name=?", (entity1,))
    row1 = c.fetchone()
    c.execute("SELECT id FROM entities WHERE name=?", (entity2,))
    row2 = c.fetchone()
    if not row1 or not row2:
        print("⚠️ 未在知识库中找到实体，跳过更新")
        conn.close()
        return
    subj_id = row1[0]
    obj_id = row2[0]
    # 查找是否存在关系（任何类型），或创建默认关系
    c.execute("SELECT id, confidence FROM relations WHERE subject_id=? AND object_id=?", (subj_id, obj_id))
    rel = c.fetchone()
    if rel:
        rel_id, old_conf = rel
        if confirmed == "yes":
            new_conf = min(old_conf + 0.2, 1.0)
        else:
            new_conf = max(old_conf - 0.2, 0.0)
        c.execute("UPDATE relations SET confidence=? WHERE id=?", (new_conf, rel_id))
    else:
        # 创建新关系，置信度根据验证结果设置
        init_conf = 0.7 if confirmed == "yes" else 0.3
        c.execute("INSERT INTO relations (subject_id, object_id, predicate, confidence, first_seen, last_seen, source_seed) VALUES (?,?,?,?,?,?,?)",
                  (subj_id, obj_id, "related", init_conf, datetime.now().isoformat(), datetime.now().isoformat(), "hypothesis_verification"))
    conn.commit()
    conn.close()
    print(f"📊 已根据验证结果更新 {entity1} 与 {entity2} 的关系置信度")

def update_knowledge_from_verification(task, success):
    """从任务标题解析实体并更新知识库（后备方案）"""
    import sqlite3
    title = task.get("title", "")
    if "因果关系" not in title:
        return
    parts = title.split()
    if len(parts) >= 4:
        e1 = parts[1]
        e2 = parts[3]
        # 去除可能的标点符号
        e1 = e1.strip('*_.,:;')
        e2 = e2.strip('*_.,:;')
        conn = sqlite3.connect(KNOWLEDGE_DB)
        c = conn.cursor()
        c.execute('''
            SELECT r.id, r.confidence
            FROM relations r
            JOIN entities e1 ON r.subject_id = e1.id
            JOIN entities e2 ON r.object_id = e2.id
            WHERE e1.name = ? AND e2.name = ?
        ''', (e1, e2))
        row = c.fetchone()
        if row:
            rid, conf = row
            new_conf = min(conf + 0.2 if success else conf - 0.2, 1.0)
            new_conf = max(new_conf, 0.0)
            c.execute("UPDATE relations SET confidence = ? WHERE id = ?", (new_conf, rid))
            print(f"📊 已更新关系 {e1}-{e2} 置信度: {conf:.2f} -> {new_conf:.2f}")
        conn.commit()
        conn.close()

def main():
    parser = argparse.ArgumentParser(description='完成任务，支持假设验证')
    parser.add_argument('task_id', type=int, help='任务ID')
    parser.add_argument('agent_id', help='完成任务的智能体ID')
    parser.add_argument('--model', help='完成任务使用的主要模型名称')
    parser.add_argument('--calls', type=int, default=1, help='模型调用次数')
    parser.add_argument('--seeds', nargs='+', help='引用的种子文件名（可多个）')
    parser.add_argument('--confirm', choices=['yes', 'no'], help='对于假设任务，验证结果')
    args = parser.parse_args()

    try:
        with open(TASKS_JSON) as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"❌ 任务文件不存在: {TASKS_JSON}")
        sys.exit(1)

    task = None
    for t in data["tasks"]:
        if t["id"] == args.task_id:
            task = t
            break

    if not task:
        print(f"❌ 未找到任务 {args.task_id}")
        sys.exit(1)

    if task.get("status") not in ("进行", "竞争"):
        print(f"❌ 任务 {args.task_id} 状态不是'进行'，当前: {task.get('status')}")
        sys.exit(1)

    participants = task.get("participants", [])
    if args.agent_id not in participants:
        print(f"❌ {args.agent_id} 不是任务 {args.task_id} 的参与者")
        sys.exit(1)

    mode = task.get("mode", "competition")

    if mode == "cooperation":
        task["completed_by"] = participants[:]
        task["status"] = "完成"
        print(f"✅ 合作任务 {args.task_id} 已完成，所有参与者共同完成: {participants}")
    else:
        task["completed_by"] = [args.agent_id]
        task["status"] = "完成"
        print(f"✅ 竞争任务 {args.task_id} 已完成，完成者: {args.agent_id}")

    if args.model:
        if "participant_models" not in task:
            task["participant_models"] = {}
        task["participant_models"][args.agent_id] = {
            "primary_model": args.model,
            "calls": args.calls,
            "all_models": [args.model]
        }

    if args.seeds:
        if "referenced_seeds" not in task:
            task["referenced_seeds"] = []
        task["referenced_seeds"].extend(args.seeds)

    # 处理假设验证（如果有 --confirm 参数）
    if task.get("type") == "验证假设" and args.confirm:
        if task.get("subtype") == "causal_counterfactual":
            update_from_causal_counterfactual(task, args.confirm)
        if task.get("subtype") == "counterfactual":
            update_from_counterfactual(task, args.confirm)
        hyp = task.get("hypothesis")
        if hyp:
            e1 = hyp.get("entity1")
            e2 = hyp.get("entity2")
            if e1 and e2:
                update_hypothesis_confidence(e1, e2, args.confirm)
                hyp["confirmed"] = (args.confirm == "yes")
            else:
                print("⚠️ 假设缺少实体信息，尝试从标题解析")
                update_knowledge_from_verification(task, args.confirm == "yes")
        else:
            print("⚠️ 任务标记为假设但缺少 hypothesis 字段，尝试从标题解析")
            update_knowledge_from_verification(task, args.confirm == "yes")
    else:
        # 如果没有提供 --confirm，但任务是验证假设，我们仍然可以尝试用成功标志（默认 true）更新
        if task.get("type") == "验证假设":
            update_knowledge_from_verification(task, True)

    task["completion_time"] = datetime.now().isoformat()
    task["last_updated"] = datetime.now().isoformat()

    with open(TASKS_JSON, 'w') as f:
        json.dump(data, f, indent=2)

if __name__ == "__main__":
    main()

# ----- 第五阶段：反事实验证反馈 -----
def update_from_counterfactual(task, confirmed):
    """根据反事实验证结果更新图谱"""
    hyp = task.get("hypothesis", {})
    e1 = hyp.get("entity1")
    e2 = hyp.get("entity2")
    if not e1 or not e2:
        return
    import sqlite3
    from pathlib import Path
    KNOWLEDGE_DB = Path.home() / "xuzhi_genesis" / "centers" / "intelligence" / "knowledge" / "knowledge.db"
    conn = sqlite3.connect(KNOWLEDGE_DB)
    c = conn.cursor()
    # 查找关系
    c.execute('''
        SELECT r.id, r.confidence
        FROM relations r
        JOIN entities e1 ON r.subject_id = e1.id
        JOIN entities e2 ON r.object_id = e2.id
        WHERE e1.name = ? AND e2.name = ?
    ''', (e1, e2))
    row = c.fetchone()
    if row:
        rid, old_conf = row
        # 反事实验证：如果验证成功（即反事实成立），则减弱原关系置信度；如果失败，则增强原关系
        if confirmed == "yes":
            new_conf = max(old_conf - 0.2, 0.0)
        else:
            new_conf = min(old_conf + 0.2, 1.0)
        c.execute("UPDATE relations SET confidence = ? WHERE id = ?", (new_conf, rid))
        print(f"📊 反事实验证更新关系 {e1}-{e2} 置信度: {old_conf:.2f} -> {new_conf:.2f}")
    conn.commit()
    conn.close()

# ----- 第五阶段：因果反事实验证反馈 -----
def update_from_causal_counterfactual(task, confirmed):
    hyp = task.get("hypothesis", {})
    cause = hyp.get("cause")
    effect = hyp.get("effect")
    if not cause or not effect:
        return
    import sqlite3
    from pathlib import Path
    KNOWLEDGE_DB = Path.home() / "xuzhi_genesis" / "centers" / "intelligence" / "knowledge" / "knowledge.db"
    conn = sqlite3.connect(KNOWLEDGE_DB)
    c = conn.cursor()
    # 查找因果关系（可能有多个，取第一个）
    c.execute('''
        SELECT r.id, r.confidence
        FROM relations r
        JOIN entities e1 ON r.subject_id = e1.id
        JOIN entities e2 ON r.object_id = e2.id
        WHERE e1.name = ? AND e2.name = ? AND r.predicate IN ('causes', 'leads to', 'increases', 'decreases', 'prevents')
    ''', (cause, effect))
    row = c.fetchone()
    if row:
        rid, old_conf = row
        # 反事实验证逻辑：如果验证成功（即反事实成立），原因果关系可能被削弱；否则加强
        if confirmed == "yes":
            new_conf = max(old_conf - 0.2, 0.0)
        else:
            new_conf = min(old_conf + 0.2, 1.0)
        c.execute("UPDATE relations SET confidence = ? WHERE id = ?", (new_conf, rid))
        print(f"📊 因果反事实验证更新 {cause}-{effect} 置信度: {old_conf:.2f} -> {new_conf:.2f}")
    conn.commit()
    conn.close()
