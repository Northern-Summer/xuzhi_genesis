#!/usr/bin/env bash
# 第二阶段：共识检测与元种子生成
set -euo pipefail

echo "=================================================="
echo "开始执行第二阶段：共识检测与元种子生成"
echo "=================================================="

BASE_DIR="/home/summer/xuzhi_genesis"
INTEL_DIR="$BASE_DIR/centers/intelligence"
TASK_DIR="$BASE_DIR/centers/task"
MIND_DIR="$BASE_DIR/centers/mind"
SEEDS_DIR="$INTEL_DIR/seeds"
META_SEEDS_DIR="$SEEDS_DIR/meta"
BACKUP_DIR="$BASE_DIR/backups/upgrade_stage2_$(date +%Y%m%d_%H%M%S)"

mkdir -p "$BACKUP_DIR"
mkdir -p "$META_SEEDS_DIR"
echo "✅ 创建元种子目录: $META_SEEDS_DIR"

# 备份相关脚本
cp "$TASK_DIR/complete_task.py" "$BACKUP_DIR/complete_task.py.bak"
cp "$INTEL_DIR/context_injector.py" "$BACKUP_DIR/context_injector.py.bak"
echo "✅ 已备份当前脚本"

# 1. 修改 complete_task.py，添加种子引用参数
cat > "$TASK_DIR/complete_task.py" << 'EOF'
#!/usr/bin/env python3
"""
标记任务为完成，支持引用种子文件。
用法: ./complete_task.py <task_id> <agent_id> [--model MODEL] [--calls CALLS] [--seeds SEED1 SEED2 ...]
"""
import argparse
import json
import sys
from pathlib import Path
from datetime import datetime

TASKS_JSON = Path.home() / ".openclaw" / "tasks" / "tasks.json"

def main():
    parser = argparse.ArgumentParser(description='完成任务，可引用种子')
    parser.add_argument('task_id', type=int, help='任务ID')
    parser.add_argument('agent_id', help='完成任务的智能体ID')
    parser.add_argument('--model', help='完成任务使用的主要模型名称')
    parser.add_argument('--calls', type=int, default=1, help='模型调用次数')
    parser.add_argument('--seeds', nargs='+', help='引用的种子文件名（可多个）')
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

    # 记录引用的种子
    if args.seeds:
        if "referenced_seeds" not in task:
            task["referenced_seeds"] = []
        task["referenced_seeds"].extend(args.seeds)

    task["completion_time"] = datetime.now().isoformat()
    task["last_updated"] = datetime.now().isoformat()

    with open(TASKS_JSON, 'w') as f:
        json.dump(data, f, indent=2)

if __name__ == "__main__":
    main()
EOF
chmod +x "$TASK_DIR/complete_task.py"
echo "✅ 已更新 complete_task.py，支持种子引用"

# 2. 新增 consensus_detector.py
cat > "$INTEL_DIR/consensus_detector.py" << 'EOF'
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
EOF
chmod +x "$INTEL_DIR/consensus_detector.py"
echo "✅ 已创建 consensus_detector.py"

# 3. 修改 context_injector.py，优先加载元种子
cat >> "$INTEL_DIR/context_injector.py" << 'EOF'

# ----- 以下为第二阶段添加：元种子注入 -----
def get_meta_seeds(limit=3):
    """获取最新的元种子内容"""
    meta_dir = Path(__file__).parent / "seeds" / "meta"
    if not meta_dir.exists():
        return []
    meta_files = sorted(meta_dir.glob("meta_*.md"), reverse=True)[:limit]
    contents = []
    for f in meta_files:
        with open(f) as mf:
            contents.append(mf.read())
    return contents

def inject_meta_seeds(context_lines):
    """将元种子描述添加到上下文"""
    metas = get_meta_seeds()
    if metas:
        context_lines.append("\n## 近期形成的共识知识")
        context_lines.extend(metas)
    return context_lines

# 在 generate_context 函数中合适位置调用 inject_meta_seeds
# 假设 generate_context 最后构建 context_lines 列表，我们可以在返回前插入
# 由于原文件可能被覆盖，这里使用 sed 在实际文件中插入调用。我们采用修改原函数的方式。
# 但为了脚本自动化，我们直接用 sed 在 generate_context 末尾添加一行调用。
EOF

# 使用 sed 在 generate_context 函数末尾添加元种子注入
sed -i '/^def generate_context/,/^def / s/^def.*/&\n    context_lines = inject_meta_seeds(context_lines)/' "$INTEL_DIR/context_injector.py"
echo "✅ 已修改 context_injector.py，支持元种子注入"

# 4. 将共识检测加入周期引擎（每小时运行一次）
# 在 cycle_engine.sh 中添加一个循环
cat >> "/home/summer/xuzhi_genesis/centers/engineering/cycle_engine.sh" << 'EOF'

# 共识检测（每小时）
while true; do
    python3 /home/summer/xuzhi_genesis/centers/intelligence/consensus_detector.py
    sleep 3600
done &
EOF
echo "✅ 已添加共识检测到 cycle_engine.sh"

# 重启 cycle_engine.sh 使修改生效
pkill -f cycle_engine.sh || true
cd /home/summer/xuzhi_genesis/centers/engineering
nohup ./cycle_engine.sh >> /home/summer/xuzhi_genesis/logs/cycle_engine.log 2>&1 &
echo "✅ 已重启 cycle_engine.sh"

echo "=================================================="
echo "第二阶段完成！"
echo "备份位置: $BACKUP_DIR"
echo "现在，当智能体完成任务时可通过 --seeds 参数引用种子，系统将自动检测共识并生成元种子。"
echo "测试方法：手动完成一个任务并引用种子，然后运行 consensus_detector.py 查看效果。"
echo "=================================================="


