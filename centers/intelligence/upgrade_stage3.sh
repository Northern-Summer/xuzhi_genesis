#!/usr/bin/env bash
# 第三阶段：假设生成与验证
set -euo pipefail

echo "=================================================="
echo "开始执行第三阶段：假设生成与验证"
echo "=================================================="

BASE_DIR="/home/summer/xuzhi_genesis"
INTEL_DIR="$BASE_DIR/centers/intelligence"
TASK_DIR="$BASE_DIR/centers/task"
MIND_DIR="$BASE_DIR/centers/mind"
CONFIG_DIR="$BASE_DIR/config"
BACKUP_DIR="$BASE_DIR/backups/upgrade_stage3_$(date +%Y%m%d_%H%M%S)"

mkdir -p "$BACKUP_DIR"
mkdir -p "$CONFIG_DIR"
echo "✅ 创建备份目录和配置目录"

# 备份相关脚本
cp "$TASK_DIR/generate_task.py" "$BACKUP_DIR/generate_task.py.bak" 2>/dev/null || true
cp "$TASK_DIR/complete_task.py" "$BACKUP_DIR/complete_task.py.bak" 2>/dev/null || true
cp "$BASE_DIR/centers/engineering/crown/wakeup_agent.sh" "$BACKUP_DIR/wakeup_agent.sh.bak" 2>/dev/null || true
echo "✅ 已备份当前脚本"

# 1. 创建假设模板配置文件
cat > "$CONFIG_DIR/hypothesis_templates.json" << 'EOF'
{
  "templates": [
    {
      "pattern": "explore_causality",
      "description": "探索 {entityA} 与 {entityB} 之间是否存在因果关系",
      "type": "验证假设",
      "department": "science"
    },
    {
      "pattern": "verify_contradiction",
      "description": "验证 '{statement}' 是否与已有知识矛盾",
      "type": "验证假设",
      "department": "philosophy"
    },
    {
      "pattern": "test_generalization",
      "description": "测试 {concept} 在 {domain} 领域中的泛化能力",
      "type": "验证假设",
      "department": "engineering"
    }
  ]
}
EOF
echo "✅ 创建假设模板配置: $CONFIG_DIR/hypothesis_templates.json"

# 2. 修改 generate_task.py，增加假设生成逻辑
cat > "$TASK_DIR/generate_task.py" << 'EOF'
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
EOF
chmod +x "$TASK_DIR/generate_task.py"
echo "✅ 已更新 generate_task.py，支持假设生成"

# 3. 修改 complete_task.py，添加验证反馈逻辑
# 我们需要在完成时如果任务类型为“验证假设”，则根据结果更新知识图谱中的置信度。
# 在原有文件基础上，在最后添加一段处理。

# 先追加函数到 complete_task.py
cat >> "$TASK_DIR/complete_task.py" << 'EOF'

# ----- 以下为第三阶段添加：验证假设反馈 -----
def update_knowledge_from_verification(task, success):
    """如果任务为验证假设，根据结果更新图谱中的关系置信度"""
    import sqlite3
    from pathlib import Path
    KNOWLEDGE_DB = Path.home() / "xuzhi_genesis" / "centers" / "intelligence" / "knowledge" / "knowledge.db"
    # 简单解析任务标题，假设标题包含实体名（实际可更复杂）
    title = task.get("title", "")
    # 这里实现简单：如果标题包含"因果关系"，我们假设它验证的是两个实体间的关系
    # 实际应用中需要更精确的映射，此处仅为示例
    if "因果关系" in title:
        # 尝试提取实体名（简化：取前两个词）
        parts = title.split()
        if len(parts) >= 4:
            e1 = parts[1]
            e2 = parts[3]
            conn = sqlite3.connect(KNOWLEDGE_DB)
            c = conn.cursor()
            # 查找这两个实体间的关系
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

# 在 main 函数最后调用（需找到合适位置插入）
# 我们将在 main 函数末尾（保存文件之后）插入调用
EOF

# 使用 sed 在 main 函数末尾（保存文件后）插入调用
sed -i '/with open(TASKS_JSON/ a\    # 验证假设反馈\n    if task.get("type") == "验证假设":\n        # 假设成功（任务完成即视为验证成功，实际可根据结果调整）\n        update_knowledge_from_verification(task, True)' "$TASK_DIR/complete_task.py"
echo "✅ 已修改 complete_task.py，支持验证反馈"

# 4. 更新 wakeup_agent.sh，确保它能调用增强版 generate_task.py（原本已调用，无需修改）

echo "=================================================="
echo "第三阶段完成！"
echo "备份位置: $BACKUP_DIR"
echo "现在，当智能体在空闲且任务少时，将尝试生成假设任务。"
echo "完成任务时，如果任务类型为'验证假设'，将自动更新知识图谱中的置信度。"
echo "测试方法：等待自动唤醒或手动运行 generate_task.py 查看是否生成假设任务。"
echo "=================================================="

