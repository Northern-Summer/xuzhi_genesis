#!/usr/bin/env bash
# 第五阶段：反事实推演
set -euo pipefail

echo "=================================================="
echo "开始执行第五阶段：反事实推演"
echo "=================================================="

BASE_DIR="/home/summer/xuzhi_genesis"
INTEL_DIR="$BASE_DIR/centers/intelligence"
TASK_DIR="$BASE_DIR/centers/task"
MIND_DIR="$BASE_DIR/centers/mind"
CONFIG_DIR="$BASE_DIR/config"
BACKUP_DIR="$BASE_DIR/backups/upgrade_stage5_$(date +%Y%m%d_%H%M%S)"

mkdir -p "$BACKUP_DIR"
mkdir -p "$CONFIG_DIR"
echo "✅ 创建备份目录和配置目录"

# 备份相关脚本
cp "$INTEL_DIR/counterfactual_generator.py" "$BACKUP_DIR/" 2>/dev/null || true
cp "$TASK_DIR/complete_task.py" "$BACKUP_DIR/complete_task.py.bak" 2>/dev/null || true
echo "✅ 已备份当前脚本"

# 1. 创建反事实生成器
cat > "$INTEL_DIR/counterfactual_generator.py" << 'EOF'
#!/usr/bin/env python3
"""
反事实推演生成器：基于知识图谱和本地模型，生成反事实假设任务。
"""
import json
import sqlite3
import random
import requests
import sys
from pathlib import Path
from datetime import datetime, timedelta

# 路径配置
KNOWLEDGE_DB = Path.home() / "xuzhi_genesis" / "centers" / "intelligence" / "knowledge" / "knowledge.db"
TASKS_JSON = Path.home() / ".openclaw" / "tasks" / "tasks.json"
LOG_FILE = Path.home() / "xuzhi_genesis" / "logs" / "counterfactual.log"
OLLAMA_URL = "http://localhost:11434/api/generate"

# 本地模型名称
MODEL = "qwen3.5:4b"

def log(msg):
    """写入日志"""
    with open(LOG_FILE, 'a') as f:
        f.write(f"[{datetime.now().isoformat()}] {msg}\n")

def load_json(path):
    with open(path) as f:
        return json.load(f)

def save_json(path, data):
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)

def get_random_entity_pair():
    """从知识图谱中随机选取一对有关系的实体（优先因果关系）"""
    conn = sqlite3.connect(KNOWLEDGE_DB)
    c = conn.cursor()
    # 先尝试找有因果关系的关系（predicate 包含 "cause" 等）
    c.execute('''
        SELECT e1.name, e2.name, r.confidence, r.predicate
        FROM relations r
        JOIN entities e1 ON r.subject_id = e1.id
        JOIN entities e2 ON r.object_id = e2.id
        WHERE r.predicate LIKE '%cause%' OR r.predicate LIKE '%lead%' OR r.predicate LIKE '%result%'
        ORDER BY RANDOM() LIMIT 1
    ''')
    row = c.fetchone()
    if row:
        conn.close()
        return row[0], row[1], row[2], row[3]
    # 如果没有明确因果关系，随机取一对关系
    c.execute('''
        SELECT e1.name, e2.name, r.confidence, r.predicate
        FROM relations r
        JOIN entities e1 ON r.subject_id = e1.id
        JOIN entities e2 ON r.object_id = e2.id
        ORDER BY RANDOM() LIMIT 1
    ''')
    row = c.fetchone()
    conn.close()
    if row:
        return row[0], row[1], row[2], row[3]
    return None, None, None, None

def generate_counterfactual(entity1, entity2, predicate, confidence):
    """调用本地模型生成反事实问题"""
    prompt = f"""基于以下已知关系生成一个反事实问题：
实体1: {entity1}
实体2: {entity2}
关系: {predicate}
置信度: {confidence}

请生成一个“如果……会怎样”的反事实问题，探索如果这个关系不成立或相反时的情况。
只输出问题本身，不要额外解释。"""
    try:
        resp = requests.post(OLLAMA_URL, json={
            "model": MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.8, "max_tokens": 100}
        }, timeout=30)
        resp.raise_for_status()
        result = resp.json()
        question = result.get("response", "").strip()
        return question
    except Exception as e:
        log(f"模型调用失败: {e}")
        return None

def create_counterfactual_task(question, entity1, entity2):
    """将反事实问题作为验证任务插入任务中心"""
    with open(TASKS_JSON) as f:
        data = json.load(f)

    new_task = {
        "id": data["next_id"],
        "title": question,
        "type": "验证假设",
        "subtype": "counterfactual",  # 新增字段，标记为反事实
        "department": "science",       # 默认给科学部
        "mode": "competition",
        "description": question,
        "hypothesis": {
            "entity1": entity1,
            "entity2": entity2,
            "relation": None,  # 可后续填充
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
    log("开始反事实生成周期")
    e1, e2, conf, pred = get_random_entity_pair()
    if not e1:
        log("图谱中无可用实体对，跳过")
        return

    question = generate_counterfactual(e1, e2, pred, conf)
    if not question:
        log("生成问题失败")
        return

    task_id = create_counterfactual_task(question, e1, e2)
    log(f"生成反事实任务 ID {task_id}: {question}")

if __name__ == "__main__":
    main()
EOF
chmod +x "$INTEL_DIR/counterfactual_generator.py"
echo "✅ 已创建反事实生成器"

# 2. 修改 complete_task.py，处理反事实任务的验证反馈
# 在适当位置插入代码，当任务类型为“验证假设”且 subtype 为“counterfactual”时，根据验证结果更新关系置信度
cat >> "$TASK_DIR/complete_task.py" << 'EOF'

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
EOF

# 在 main 函数中，当任务为反事实时调用上述函数
# 我们将在处理假设验证的代码块中增加判断
sed -i '/if task.get("type") == "验证假设" and args.confirm:/a \            if task.get("subtype") == "counterfactual":\n                update_from_counterfactual(task, args.confirm)' "$TASK_DIR/complete_task.py"

echo "✅ 已修改 complete_task.py，支持反事实验证反馈"

# 3. 将反事实生成加入周期引擎（每6小时运行一次）
cat >> "/home/summer/xuzhi_genesis/centers/engineering/cycle_engine.sh" << 'EOF'

# 反事实推演生成（每6小时）
while true; do
    python3 /home/summer/xuzhi_genesis/centers/intelligence/counterfactual_generator.py
    sleep 21600  # 6小时
done &
EOF
echo "✅ 已添加反事实生成到 cycle_engine.sh"

# 重启 cycle_engine.sh
pkill -f cycle_engine.sh || true
cd /home/summer/xuzhi_genesis/centers/engineering
nohup ./cycle_engine.sh >> /home/summer/xuzhi_genesis/logs/cycle_engine.log 2>&1 &
echo "✅ 已重启 cycle_engine.sh"

echo "=================================================="
echo "第五阶段完成！"
echo "备份位置: $BACKUP_DIR"
echo "反事实生成器已部署，每6小时运行一次。"
echo "可以手动测试："
echo "  python3 $INTEL_DIR/counterfactual_generator.py"
echo "  # 查看生成的任务"
echo "  jq '.tasks | last' /home/summer/.openclaw/tasks/tasks.json"
echo "=================================================="
