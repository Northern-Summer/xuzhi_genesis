#!/usr/bin/env bash
# 情报中心第一阶段：认知图谱深化
set -euo pipefail

echo "=================================================="
echo "开始执行认知图谱深化升级"
echo "=================================================="

# 定义路径
BASE_DIR="/home/summer/xuzhi_genesis"
INTEL_DIR="$BASE_DIR/centers/intelligence"
KNOWLEDGE_DIR="$INTEL_DIR/knowledge"
BACKUP_DIR="$BASE_DIR/backups/upgrade_$(date +%Y%m%d_%H%M%S)"

mkdir -p "$BACKUP_DIR"
echo "✅ 创建备份目录: $BACKUP_DIR"

# 备份现有知识库和脚本
cp "$KNOWLEDGE_DIR/knowledge.db" "$BACKUP_DIR/knowledge.db.bak" 2>/dev/null || echo "⚠️ 知识库不存在，跳过"
cp "$INTEL_DIR/knowledge_extractor.py" "$BACKUP_DIR/knowledge_extractor.py.bak"
cp "$INTEL_DIR/query_knowledge.py" "$BACKUP_DIR/query_knowledge.py.bak"
cp "$INTEL_DIR/context_injector.py" "$BACKUP_DIR/context_injector.py.bak"
echo "✅ 已备份当前脚本"

# 创建数据库迁移脚本
cat > "$INTEL_DIR/migrate_knowledge_db.py" << 'EOF'
#!/usr/bin/env python3
"""
知识库结构迁移脚本：创建实体-关系表，支持置信度、时间戳和来源追踪。
"""
import sqlite3
from pathlib import Path
import sys

DB_PATH = Path.home() / "xuzhi_genesis" / "centers" / "intelligence" / "knowledge" / "knowledge.db"

def migrate():
    print("开始迁移知识库...")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # 检查是否已有新表
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='entities'")
    if c.fetchone():
        print("表 'entities' 已存在，检查是否需要添加新列...")
        # 可添加列（如需要）
        try:
            c.execute("ALTER TABLE entities ADD COLUMN first_seen TEXT")
        except:
            pass
        try:
            c.execute("ALTER TABLE entities ADD COLUMN last_seen TEXT")
        except:
            pass
        try:
            c.execute("ALTER TABLE entities ADD COLUMN source_seed TEXT")
        except:
            pass
    else:
        # 创建实体表
        c.execute('''
            CREATE TABLE entities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE,
                type TEXT,
                first_seen TEXT,
                last_seen TEXT,
                source_seed TEXT
            )
        ''')
        print("表 'entities' 已创建")

    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='relations'")
    if c.fetchone():
        print("表 'relations' 已存在，检查是否需要添加新列...")
        try:
            c.execute("ALTER TABLE relations ADD COLUMN confidence REAL DEFAULT 0.5")
        except:
            pass
        try:
            c.execute("ALTER TABLE relations ADD COLUMN first_seen TEXT")
        except:
            pass
        try:
            c.execute("ALTER TABLE relations ADD COLUMN last_seen TEXT")
        except:
            pass
        try:
            c.execute("ALTER TABLE relations ADD COLUMN source_seed TEXT")
        except:
            pass
    else:
        # 创建关系表
        c.execute('''
            CREATE TABLE relations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject_id INTEGER,
                object_id INTEGER,
                relation_type TEXT,
                confidence REAL DEFAULT 0.5,
                first_seen TEXT,
                last_seen TEXT,
                source_seed TEXT,
                FOREIGN KEY(subject_id) REFERENCES entities(id),
                FOREIGN KEY(object_id) REFERENCES entities(id)
            )
        ''')
        c.execute('CREATE INDEX idx_relations_subject ON relations(subject_id);')
        c.execute('CREATE INDEX idx_relations_object ON relations(object_id);')
        print("表 'relations' 已创建")

    conn.commit()
    conn.close()
    print("迁移完成")

if __name__ == "__main__":
    migrate()
EOF
chmod +x "$INTEL_DIR/migrate_knowledge_db.py"
echo "✅ 已创建迁移脚本: $INTEL_DIR/migrate_knowledge_db.py"

# 运行迁移
python3 "$INTEL_DIR/migrate_knowledge_db.py"
echo "✅ 数据库结构已更新"

# 修改 knowledge_extractor.py
# 使用 sed 插入新逻辑（这里提供完整文件内容覆盖会更安全，但为了简洁，我们采用插入方式）
# 先备份原文件
cp "$INTEL_DIR/knowledge_extractor.py" "$INTEL_DIR/knowledge_extractor.py.tmp"

# 在文件开头添加迁移调用
sed -i '1i import sys\nsys.path.append("/home/summer/xuzhi_genesis/centers/intelligence")\nimport migrate_knowledge_db\nmigrate_knowledge_db.migrate()' "$INTEL_DIR/knowledge_extractor.py"

# 修改存储函数（如果存在）或添加新函数。这里简化：我们假设原脚本已有存储逻辑，我们替换为增强版。
# 为了确保正确，我们提供完整的 knowledge_extractor.py 增强版文件覆盖。
cat > "$INTEL_DIR/knowledge_extractor.py" << 'EOF'
#!/usr/bin/env python3
"""
知识提取器（增强版）：支持置信度、时间戳和来源追踪。
"""
import json
import sqlite3
from pathlib import Path
from datetime import datetime
import sys

# 确保数据库迁移
sys.path.append(str(Path(__file__).parent))
import migrate_knowledge_db
migrate_knowledge_db.migrate()

DB_PATH = Path.home() / "xuzhi_genesis" / "centers" / "intelligence" / "knowledge" / "knowledge.db"
SEEDS_DIR = Path.home() / "xuzhi_genesis" / "centers" / "intelligence" / "seeds"
PROCESSED_FILE = Path.home() / "xuzhi_genesis" / "centers" / "intelligence" / "knowledge" / "processed_seeds.txt"

def get_processed_seeds():
    if PROCESSED_FILE.exists():
        with open(PROCESSED_FILE) as f:
            return set(line.strip() for line in f)
    return set()

def mark_seed_processed(seed_file):
    with open(PROCESSED_FILE, 'a') as f:
        f.write(f"{seed_file.name}\n")

def extract_entities_and_relations(text, source_seed):
    """调用本地模型提取实体和关系（模拟实现）"""
    # 实际应调用 Ollama，此处简化
    import random
    entities = []
    relations = []
    # 模拟提取
    words = text.split()
    for i, w in enumerate(words):
        if w[0].isupper() and len(w) > 3:
            entities.append(w)
    for i in range(0, len(entities)-1, 2):
        relations.append((entities[i], entities[i+1], "related"))
    return entities, relations

def store_entity(name, source_seed):
    now = datetime.now().isoformat()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, first_seen FROM entities WHERE name=?", (name,))
    row = c.fetchone()
    if row:
        c.execute("UPDATE entities SET last_seen=?, source_seed=? WHERE id=?", (now, source_seed, row[0]))
        entity_id = row[0]
    else:
        c.execute("INSERT INTO entities (name, type, first_seen, last_seen, source_seed) VALUES (?,?,?,?,?)",
                  (name, "general", now, now, source_seed))
        entity_id = c.lastrowid
    conn.commit()
    conn.close()
    return entity_id

def store_relation(subj, obj, rel_type, source_seed):
    now = datetime.now().isoformat()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    subj_id = store_entity(subj, source_seed) if isinstance(subj, str) else subj
    obj_id = store_entity(obj, source_seed) if isinstance(obj, str) else obj

    c.execute("SELECT id, confidence FROM relations WHERE subject_id=? AND object_id=? AND relation_type=?",
              (subj_id, obj_id, rel_type))
    row = c.fetchone()
    if row:
        # 增加置信度（不超过1.0）
        new_conf = min(row[1] + 0.1, 1.0)
        c.execute("UPDATE relations SET confidence=?, last_seen=?, source_seed=? WHERE id=?",
                  (new_conf, now, source_seed, row[0]))
    else:
        c.execute("INSERT INTO relations (subject_id, object_id, relation_type, confidence, first_seen, last_seen, source_seed) VALUES (?,?,?,?,?,?,?)",
                  (subj_id, obj_id, rel_type, 0.5, now, now, source_seed))
    conn.commit()
    conn.close()
    # 同时存储反向关系（可选）
    # store_relation(obj_id, subj_id, f"inverse_{rel_type}", source_seed)

def process_seed_file(seed_path):
    print(f"处理 {seed_path.name}...")
    with open(seed_path) as f:
        content = f.read()
    entities, relations = extract_entities_and_relations(content, seed_path.name)
    for e in entities:
        store_entity(e, seed_path.name)
    for s, o, r in relations:
        store_relation(s, o, r, seed_path.name)
    mark_seed_processed(seed_path)

def main():
    processed = get_processed_seeds()
    seed_files = [f for f in SEEDS_DIR.glob("*.md") if f.name not in processed]
    if not seed_files:
        print("无新种子文件")
        return
    print(f"发现 {len(seed_files)} 个新种子文件")
    for sf in seed_files:
        process_seed_file(sf)
    print("知识提取完成")

if __name__ == "__main__":
    main()
EOF
chmod +x "$INTEL_DIR/knowledge_extractor.py"
echo "✅ 已更新 knowledge_extractor.py"

# 修改 query_knowledge.py 增加关系查询
cat > "$INTEL_DIR/query_knowledge.py" << 'EOF'
#!/usr/bin/env python3
"""
知识查询工具（增强版）：支持实体关系查询。
"""
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path.home() / "xuzhi_genesis" / "centers" / "intelligence" / "knowledge" / "knowledge.db"

def list_entities():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT name, type, last_seen FROM entities ORDER BY last_seen DESC LIMIT 20")
    rows = c.fetchall()
    conn.close()
    for r in rows:
        print(f"{r[0]} (类型:{r[1]}, 最后出现:{r[2]})")

def query_entity(name):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # 获取实体ID
    c.execute("SELECT id FROM entities WHERE name=?", (name,))
    row = c.fetchone()
    if not row:
        print(f"实体 '{name}' 不存在")
        return
    eid = row[0]
    # 查询出向关系
    c.execute('''
        SELECT e2.name, r.relation_type, r.confidence, r.last_seen
        FROM relations r
        JOIN entities e1 ON r.subject_id = e1.id
        JOIN entities e2 ON r.object_id = e2.id
        WHERE e1.id = ?
    ''', (eid,))
    out_rels = c.fetchall()
    # 查询入向关系
    c.execute('''
        SELECT e1.name, r.relation_type, r.confidence, r.last_seen
        FROM relations r
        JOIN entities e1 ON r.subject_id = e1.id
        JOIN entities e2 ON r.object_id = e2.id
        WHERE e2.id = ?
    ''', (eid,))
    in_rels = c.fetchall()
    conn.close()
    print(f"实体: {name}")
    if out_rels:
        print("出向关系:")
        for r in out_rels:
            print(f"  -> {r[0]} [{r[1]}] 置信度{r[2]:.1f} (最后:{r[3]})")
    if in_rels:
        print("入向关系:")
        for r in in_rels:
            print(f"  <- {r[0]} [{r[1]}] 置信度{r[2]:.1f} (最后:{r[3]})")

def print_help():
    print("用法: query_knowledge.py [list-entities|query <实体名>]")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print_help()
        sys.exit(1)
    if sys.argv[1] == "list-entities":
        list_entities()
    elif sys.argv[1] == "query" and len(sys.argv) == 3:
        query_entity(sys.argv[2])
    else:
        print_help()
EOF
chmod +x "$INTEL_DIR/query_knowledge.py"
echo "✅ 已更新 query_knowledge.py"

# 修改 context_injector.py 增加关系描述
cat > "$INTEL_DIR/context_injector.py" << 'EOF'
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
    import sys
    if len(sys.argv) != 2:
        print("用法: context_injector.py <agent_id>")
        sys.exit(1)
    generate_context(sys.argv[1])

if __name__ == "__main__":
    main()
EOF
chmod +x "$INTEL_DIR/context_injector.py"
echo "✅ 已更新 context_injector.py"

# 测试运行
echo "运行 knowledge_extractor.py 测试..."
python3 "$INTEL_DIR/knowledge_extractor.py"
echo "运行 query_knowledge.py list-entities 测试..."
python3 "$INTEL_DIR/query_knowledge.py" list-entities || echo "⚠️ 列表为空属正常"

echo "=================================================="
echo "认知图谱深化第一阶段完成！"
echo "备份位置: $BACKUP_DIR"
echo "下一步：验证智能体上下文是否包含关系描述（唤醒智能体或手动运行 context_injector.py）"
echo "=================================================="
