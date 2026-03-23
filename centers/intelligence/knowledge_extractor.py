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
EXCLUDE_SUBDIRS = {"library", "meta", "archive"}

# ──────────────────────────────────────────────────────────────
# 图书馆门禁：基于元数据的启发式过滤
# 知识库只进"结构化知识"，不进"叙述性文本"
# ──────────────────────────────────────────────────────────────

L1_WHITELIST_PATTERNS = [
    re.compile(r"arxiv\.org", re.I),
    re.compile(r"nature\.com|nature\.org", re.I),
    re.compile(r"science\.org", re.I),
    re.compile(r"biorxiv\.org|medrxiv\.org", re.I),
    re.compile(r"openai\.com|anthropic\.com|deepmind\.com", re.I),
    re.compile(r"huggingface\.co", re.I),
    re.compile(r"wikipedia\.org|wikidata\.org", re.I),
    re.compile(r"nist\.gov|iso\.org|ieee\.org|w3\.org", re.I),
    re.compile(r"technologyreview\.com|quantamagazine\.org", re.I),
    re.compile(r"academic\.oup\.com|pnas\.org|plos\.org", re.I),
    re.compile(r"github\.com/.*/(blob|tree)/", re.I),
    re.compile(r"cnki\.net|wanfangdata\.com", re.I),
]

L1_BLACKLIST_PATTERNS = [
    re.compile(r"z-library|books\.lib|ebook|pdfdrive", re.I),
    re.compile(r"小说|文学|散文|诗歌|剧本", re.I),
    re.compile(r"克里希那穆提|古尔纳|村上春树", re.I),
    re.compile(r"哲学|灵修|觉醒|开悟", re.I),
    re.compile(r"SAN.*分享书籍|地址\.txt", re.I),
    re.compile(r"知乎|豆瓣|公众号|个人博客", re.I),
]

def is_library_allowed(source_meta: str) -> bool:
    """基于source元数据决定是否允许library文件进入知识处理流程"""
    for p in L1_BLACKLIST_PATTERNS:
        if p.search(source_meta):
            return False
    for p in L1_WHITELIST_PATTERNS:
        if p.search(source_meta):
            return True
    return False  # 默认拒绝不明来源

  # 排除文学/元数据/归档目录
PROCESSED_FILE = Path.home() / "xuzhi_genesis" / "centers" / "intelligence" / "knowledge" / "processed_seeds.txt"

# 因果关键词（中文和英文）
CAUSAL_KEYWORDS = [
    "导致", "引发", "使得", "造成", "引起", "产生",
    "causes", "leads to", "results in", "triggers", "increases", "decreases",
    "抑制", "阻碍", "防止", "prevents", "inhibits", "reduces"
]

# 是否使用本地模型（若安装 ollama 且模型可用，可设为 True）
USE_OLLAMA = False  # Ollama 未运行，使用正则模式

def get_processed_seeds():
    if PROCESSED_FILE.exists():
        with open(PROCESSED_FILE) as f:
            return set(line.strip() for line in f)
    return set()

def mark_seed_processed(seed_file):
    with open(PROCESSED_FILE, 'a') as f:
        f.write(f"{seed_file.name}\n")

def call_ollama(prompt):
    """调用本地 Ollama 模型（HTTP API）"""
    import urllib.request, json
    model = 'qwen3.5:4b'
    body = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode()
    req = urllib.request.Request(
        "http://localhost:11434/api/generate",
        data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            return json.loads(resp.read())["response"].strip()
    except Exception as e:
        print(f"Ollama API 失败: {e}")
        return ""

PREDICATE_VOCABULARY = [
    "supports",       # 论据/数据支持论点
    "contradicts",   # 否定/矛盾
    "uses",           # 使用/采用方法
    "explains",       # 解释现象
    "predicts",       # 预测结果
    "measures",       # 测量/量化
    "develops",       # 发展/提出
    "critiques",      # 批评/质疑
    "applies",        # 应用于
    "based_on",       # 基于
    "demonstrates",   # 论证/展示
    "correlates_with",# 相关
    "causes",         # 因果导致
    "part_of",        # 组成部分
    "precedes",       # 时间先于
    "refines",        # 精炼/细化
    "extends",        # 扩展
    "validates",      # 验证
    "introduces",     # 引入/介绍
]

def extract_with_ollama(text):
    """使用 Ollama 提取实体和关系（可选）"""
    pred_list = ", ".join(PREDICATE_VOCABULARY)
    prompt = f"""从以下文本中提取实体和它们之间的关系。

要求：
1. 只使用以下语义谓词（不可用"related"）：{pred_list}
2. 每个关系必须从上述列表中选择最准确的一个谓词
3. 实体类型：technology, concept, organization, person, method, finding, data
4. 只返回 JSON：{{"entities": [{{"name": "...", "type": "..."}}], "relations": [{{"subject": "...", "object": "...", "relation_type": "...", "is_causal": true/false}}]}}

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

def store_entities_batch(entity_names, source_seed):
    """批量存储实体（单次事务）"""
    if not entity_names:
        return {}
    now = datetime.now().isoformat()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    name_to_id = {}
    for name in entity_names:
        c.execute("SELECT id FROM entities WHERE name=?", (name,))
        row = c.fetchone()
        if row:
            c.execute("UPDATE entities SET last_seen=?, source_seed=? WHERE id=?", (now, source_seed, row[0]))
            name_to_id[name] = row[0]
        else:
            c.execute("INSERT INTO entities (name, type, first_seen, last_seen, source_seed) VALUES (?,?,?,?,?)",
                      (name, "general", now, now, source_seed))
            name_to_id[name] = c.lastrowid
    conn.commit()
    conn.close()
    return name_to_id

def store_relations_batch(relations_with_ids, source_seed):
    """批量存储关系（单次事务）"""
    if not relations_with_ids:
        return
    now = datetime.now().isoformat()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    for subj_id, obj_id, rel_type, is_causal in relations_with_ids:
        c.execute("SELECT id, confidence, is_causal FROM relations WHERE subject_id=? AND object_id=? AND predicate=?",
                  (subj_id, obj_id, rel_type))
        row = c.fetchone()
        if row:
            new_conf = min(row[1] + 0.1, 1.0)
            new_is_causal = row[2] or is_causal
            c.execute("UPDATE relations SET confidence=?, last_seen=?, source_seed=?, is_causal=? WHERE id=?",
                      (new_conf, now, source_seed, new_is_causal, row[0]))
        else:
            c.execute("INSERT INTO relations (subject_id, object_id, predicate, confidence, first_seen, last_seen, source_seed, is_causal) VALUES (?,?,?,?,?,?,?,?)",
                      (subj_id, obj_id, rel_type, 0.5, now, now, source_seed, is_causal))
    conn.commit()
    conn.close()

def process_seed_file(seed_path):
    print(f"处理 {seed_path.name}...", flush=True)
    with open(seed_path, 'r', encoding='utf-8') as f:
        content = f.read()
    entities, relations = extract_entities_and_relations(content, seed_path.name)
    # 收集所有涉及的实体名（用于ID解析）
    entity_names = list(set(entities))
    # 批量存储实体，获取 name→id 映射
    name_to_id = store_entities_batch(entity_names, seed_path.name)
    # 转换 relations 中的字符串实体为 ID
    relations_with_ids = []
    for subj, obj, rel_type, is_causal in relations:
        if subj in name_to_id and obj in name_to_id:
            relations_with_ids.append((name_to_id[subj], name_to_id[obj], rel_type, is_causal))
    # 批量存储关系
    store_relations_batch(relations_with_ids, seed_path.name)
    mark_seed_processed(seed_path)
    print(f"  → {len(entity_names)} 实体, {len(relations_with_ids)} 关系已存储", flush=True)

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
