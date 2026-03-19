#!/usr/bin/env python3
"""
上下文注入器（增强版）：为智能体生成包含实体关系描述的上下文。
"""
import json
import sqlite3
from pathlib import Path
from datetime import datetime

DB_PATH = Path.home() / "xuzhi_genesis" / "centers" / "intelligence" / "knowledge" / "knowledge.db"
AGENTS_BASE = Path.home() / ".openclaw" / "agents"

def get_recent_entities(agent_id, limit=5):
    """从任务历史中获取智能体最近关注的实体（模拟）"""
    # 实际应从任务文件中提取，这里简化返回空
    return ["AI", "scaling laws", "transformer"]  # 示例

def get_related_entities(entity_name):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id FROM entities WHERE name=?", (entity_name,))
    row = c.fetchone()
    if not row:
        conn.close()
        return []
    eid = row[0]
    # 获取出向关系
    c.execute('''
        SELECT e2.name, r.relation_type, r.confidence
        FROM relations r
        JOIN entities e1 ON r.subject_id = e1.id
        JOIN entities e2 ON r.object_id = e2.id
        WHERE e1.id = ?
        ORDER BY r.confidence DESC
        LIMIT 5
    ''', (eid,))
    out_rels = c.fetchall()
    # 获取入向关系
    c.execute('''
        SELECT e1.name, r.relation_type, r.confidence
        FROM relations r
        JOIN entities e1 ON r.subject_id = e1.id
        JOIN entities e2 ON r.object_id = e2.id
        WHERE e2.id = ?
        ORDER BY r.confidence DESC
        LIMIT 5
    ''', (eid,))
    in_rels = c.fetchall()
    conn.close()
    return out_rels + in_rels  # 合并

def generate_context(agent_id):
    context_lines = inject_meta_seeds(context_lines)
    recent = get_recent_entities(agent_id)
    context_lines = []
    for ent in recent:
        rels = get_related_entities(ent)
        if rels:
            desc = f"{ent} 的相关知识: " + "; ".join([f"{r[1]} {r[0]} (置信度{r[2]:.1f})" for r in rels[:3]])
            context_lines.append(desc)
    context = "\n".join(context_lines)

    # 写入智能体的 system_dynamic.md
    agent_dir = AGENTS_BASE / agent_id
    agent_dir.mkdir(parents=True, exist_ok=True)
    target = agent_dir / "system_dynamic.md"
    with open(target, 'w') as f:
        f.write(f"# 动态上下文 - {datetime.now().isoformat()}\n\n")
        f.write(context if context else "暂无相关实体关系")
    print(f"✅ 已为智能体 {agent_id} 生成上下文: {target}")

def main():
    context_lines = inject_meta_seeds(context_lines)
    import sys
    if len(sys.argv) != 2:
        print("用法: context_injector.py <agent_id>")
        sys.exit(1)
    generate_context(sys.argv[1])

if __name__ == "__main__":
    main()

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
    context_lines = inject_market_recommendations(context_lines, agent_id)
    return context_lines

# 在 generate_context 函数中合适位置调用 inject_meta_seeds
# 假设 generate_context 最后构建 context_lines 列表，我们可以在返回前插入
# 由于原文件可能被覆盖，这里使用 sed 在实际文件中插入调用。我们采用修改原函数的方式。
# 但为了脚本自动化，我们直接用 sed 在 generate_context 末尾添加一行调用。

# ----- 第四阶段：市场推荐 -----
def get_market_recommendations(agent_id, limit=3):
    """获取市场上与智能体可能相关的知识（随机推荐）"""
    import json
    market_script = Path(__file__).parent / "knowledge_market.py"
    # 简单调用 market 脚本查询
    # 这里用 subprocess 调用 market list，但为了避免性能问题，直接读取 listings 目录
    listings_dir = Path(__file__).parent / "knowledge_market" / "listings"
    if not listings_dir.exists():
        return []
    recs = []
    for lf in list(listings_dir.glob("*.json"))[:limit]:
        with open(lf) as f:
            listing = json.load(f)
        if listing["seller"] != agent_id:
            recs.append(f"可购买知识: {listing['filename']} (卖家 {listing['seller']}, 价格 {listing['price']})")
    return recs

def inject_market_recommendations(context_lines, agent_id):
    recs = get_market_recommendations(agent_id)
    if recs:
        context_lines.append("\n## 知识市场推荐")
        context_lines.extend(recs)
    context_lines = inject_market_recommendations(context_lines, agent_id)
    return context_lines

# 修改 generate_context 函数，在返回前调用注入
# 由于原文件可能已存在，我们通过 sed 在函数末尾添加调用
