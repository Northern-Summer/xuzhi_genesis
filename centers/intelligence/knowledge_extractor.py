#!/usr/bin/env python3
"""
知识提取器（真实因果版）：从种子文件中提取实体和关系，识别因果关系。
使用因果关键词 + 可选 Ollama 增强。
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
EXCLUDE_SUBDIRS = {"library", "meta", "archive"}  # 排除文学/元数据/归档目录
PROCESSED_FILE = Path.home() / "xuzhi_genesis" / "centers" / "intelligence" / "knowledge" / "processed_seeds.txt"

# 因果关键词（中文和英文）
CAUSAL_KEYWORDS = [
    "导致", "引发", "使得", "造成", "引起", "产生",
    "causes", "leads to", "results in", "triggers", "increases", "decreases",
    "抑制", "阻碍", "防止", "prevents", "inhibits", "reduces"
]

# 是否使用本地模型（若安装 ollama 且模型可用，可设为 True）
USE_OLLAMA = False  # 如需启用，请改为 True 并确保 ollama 运行

def get_processed_seeds():
    if PROCESSED_FILE.exists():
        with open(PROCESSED_FILE) as f:
            return set(line.strip() for line in f)
    return set()

def mark_seed_processed(seed_file):
    with open(PROCESSED_FILE, 'a') as f:
        f.write(f"{seed_file.name}\n")

def call_ollama(prompt):
    """调用本地 Ollama 模型（需 ollama 库）"""
    try:
        import ollama
        response = ollama.generate(model='qwen3.5:4b', prompt=prompt, stream=False)
        return response['response']
    except Exception as e:
        print(f"Ollama 调用失败: {e}")
        return ""

def extract_with_ollama(text):
    """使用 Ollama 提取实体和关系（可选）"""
    prompt = f"""从以下文本中提取实体和它们之间的关系。返回 JSON 格式，包含 entities 列表（每个元素有 name 和 type）和 relations 列表（每个元素有 subject, object, relation_type, is_causal）。只返回 JSON，不要其他内容。

文本：{text[:3000]}
"""
    result = call_ollama(prompt)
    if result:
        try:
            # 尝试解析 JSON
            import json
            data = json.loads(result)
            entities = data.get('entities', [])
            relations = data.get('relations', [])
            return entities, relations
        except:
            pass
    return [], []

def extract_with_regex(text):
    """基于正则和关键词的实体关系提取（备选）"""
    # 简单实体识别：大写单词、引号内的短语
    entities = set()
    # 匹配可能的大写实体（英文）
    for match in re.finditer(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', text):
        entities.add(match.group())
    # 匹配中文书名号或引号内容
    for match in re.finditer(r'[「」“”《》]([^「」“”《》]+)[「」“”《》]', text):
        entities.add(match.group(1))
    # 匹配连续的中文字符（可能为术语）
    for match in re.finditer(r'[\u4e00-\u9fa5]{2,}', text):
        entities.add(match.group())
    
    # 关系提取：简单规则——如果两个实体出现在同一句子中，且包含因果关键词，则标记为因果
    relations = []
    sentences = re.split(r'[。！？.!?]', text)
    for sent in sentences:
        sent_entities = [e for e in entities if e in sent]
        if len(sent_entities) >= 2:
            # 检查因果关键词
            is_causal = any(kw in sent for kw in CAUSAL_KEYWORDS)
            rel_type = "causes" if is_causal else "related"
            # 生成两两关系（简化：取前两个）
            for i in range(len(sent_entities)-1):
                relations.append((sent_entities[i], sent_entities[i+1], rel_type, is_causal))
    return list(entities), relations

def extract_entities_and_relations(text, source_seed):
    """主提取函数：优先使用 Ollama（若启用），否则用正则"""
    if USE_OLLAMA:
        entities, relations = extract_with_ollama(text)
        if entities:
            # 转换 relations 格式为 (subj, obj, rel_type, is_causal)
            formatted_relations = []
            for r in relations:
                subj = r.get('subject')
                obj = r.get('object')
                rel_type = r.get('relation_type', 'related')
                is_causal = r.get('is_causal', False)
                if subj and obj:
                    formatted_relations.append((subj, obj, rel_type, is_causal))
            return entities, formatted_relations
    
    # 默认使用正则
    return extract_with_regex(text)

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

def store_relation(subj, obj, rel_type, is_causal, source_seed):
    now = datetime.now().isoformat()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    subj_id = store_entity(subj, source_seed) if isinstance(subj, str) else subj
    obj_id = store_entity(obj, source_seed) if isinstance(obj, str) else obj

    # 检查是否存在相同关系
    c.execute("SELECT id, confidence, is_causal FROM relations WHERE subject_id=? AND object_id=? AND predicate=?",
              (subj_id, obj_id, rel_type))
    row = c.fetchone()
    if row:
        # 如果已存在，更新置信度和因果标志
        new_conf = min(row[1] + 0.1, 1.0)
        new_is_causal = row[2] or is_causal  # 保留因果标记
        c.execute("UPDATE relations SET confidence=?, last_seen=?, source_seed=?, is_causal=? WHERE id=?",
                  (new_conf, now, source_seed, new_is_causal, row[0]))
    else:
        c.execute("INSERT INTO relations (subject_id, object_id, predicate, confidence, first_seen, last_seen, source_seed, is_causal) VALUES (?,?,?,?,?,?,?,?)",
                  (subj_id, obj_id, rel_type, 0.5, now, now, source_seed, is_causal))
    conn.commit()
    conn.close()

def process_seed_file(seed_path):
    print(f"处理 {seed_path.name}...")
    with open(seed_path, 'r', encoding='utf-8') as f:
        content = f.read()
    entities, relations = extract_entities_and_relations(content, seed_path.name)
    # 存储实体
    for e in entities:
        store_entity(e, seed_path.name)
    # 存储关系
    for subj, obj, rel_type, is_causal in relations:
        store_relation(subj, obj, rel_type, is_causal, seed_path.name)
    mark_seed_processed(seed_path)

def main():
    processed = get_processed_seeds()
    seed_files = []
    # 递归搜索所有子目录下的 .md 文件（包括 library 子目录）
    for seed_path in SEEDS_DIR.rglob("*.md"):
        if seed_path.name not in processed:
            seed_files.append(seed_path)
    if not seed_files:
        print("无新种子文件")
        return
    print(f"发现 {len(seed_files)} 个新种子文件")
    for sf in seed_files:
        process_seed_file(sf)
    print("知识提取完成")

if __name__ == "__main__":
    main()
