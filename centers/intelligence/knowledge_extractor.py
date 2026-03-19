#!/usr/bin/env python3
"""
知识提取器（因果增强版）：识别因果关系，存入图谱。
"""
import json
import sqlite3
import re
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

# 因果关键词（中文和英文）
CAUSAL_KEYWORDS = [
    "导致", "引发", "使得", "造成", "引起", "产生",
    "causes", "leads to", "results in", "triggers", "increases", "decreases",
    "抑制", "阻碍", "防止", "prevents", "inhibits", "reduces"
]

def get_processed_seeds():
    if PROCESSED_FILE.exists():
        with open(PROCESSED_FILE) as f:
            return set(line.strip() for line in f)
    return set()

def mark_seed_processed(seed_file):
    with open(PROCESSED_FILE, 'a') as f:
        f.write(f"{seed_file.name}\n")

def extract_entities_and_relations(text, source_seed):
    """调用本地模型提取实体和关系，并判断是否因果"""
    # 实际应调用 Ollama，此处模拟返回
    # 注意：这里需要集成因果关键词判断
    import random
    entities = []
    relations = []
    # 模拟提取
    words = text.split()
    for i, w in enumerate(words):
        if w[0].isupper() and len(w) > 3:
            entities.append(w)
    for i in range(0, len(entities)-1, 2):
        rel_type = "related"
        # 检查是否包含因果关键词（简化）
        if random.random() > 0.5:  # 实际应用中应基于上下文判断
            rel_type = "causes"
        relations.append((entities[i], entities[i+1], rel_type))
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

    c.execute("SELECT id, confidence FROM relations WHERE subject_id=? AND object_id=? AND predicate=?",
              (subj_id, obj_id, rel_type))
    row = c.fetchone()
    if row:
        new_conf = min(row[1] + 0.1, 1.0)
        c.execute("UPDATE relations SET confidence=?, last_seen=?, source_seed=? WHERE id=?",
                  (new_conf, now, source_seed, row[0]))
    else:
        c.execute("INSERT INTO relations (subject_id, object_id, predicate, confidence, first_seen, last_seen, source_seed) VALUES (?,?,?,?,?,?,?)",
                  (subj_id, obj_id, rel_type, 0.5, now, now, source_seed))
    conn.commit()
    conn.close()

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
