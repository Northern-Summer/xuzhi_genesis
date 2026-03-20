#!/bin/bash
#
# deploy_knowledge_engine_fixed.sh - 部署知识提炼引擎（第四阶段第一步，修正版）
# 使用 qwen3.5:4b 模型
#

set -e

PROJECT_ROOT="/home/summer/xuzhi_genesis"
INTEL_DIR="$PROJECT_ROOT/centers/intelligence"
SEEDS_DIR="$INTEL_DIR/seeds"
KNOWLEDGE_DIR="$INTEL_DIR/knowledge"
BACKUP_DIR="$PROJECT_ROOT/backups/knowledge_engine_$(date +%Y%m%d%H%M%S)"

echo -e "\033[0;34m========================================\033[0m"
echo -e "\033[0;34m  第四阶段·第一步：知识提炼引擎（修正版）\033[0m"
echo -e "\033[0;34m========================================\033[0m\n"

# 创建知识图谱目录
mkdir -p "$KNOWLEDGE_DIR"
echo -e "\033[0;32m✅ 知识图谱目录: $KNOWLEDGE_DIR\033[0m"

# 检查 Ollama 并拉取模型
echo -e "\n\033[0;33m▶ 检查 Ollama 和模型 qwen3.5:4b...\033[0m"
if command -v ollama &> /dev/null; then
    echo -e "\033[0;32m✅ Ollama 已安装\033[0m"
    # 检查模型是否存在，不存在则拉取
    if ollama list | grep -q "qwen3.5:4b"; then
        echo -e "\033[0;32m✅ 模型 qwen3.5:4b 已存在\033[0m"
    else
        echo -e "\033[0;33m⚠️ 模型未找到，正在拉取（约 3.4GB）...\033[0m"
        ollama pull qwen3.5:4b
        echo -e "\033[0;32m✅ 模型拉取完成\033[0m"
    fi
else
    echo -e "\033[0;31m❌ Ollama 未安装，请先安装：https://ollama.com\033[0m"
    exit 1
fi

# 安装 Python 依赖
echo -e "\n\033[0;33m▶ 检查 Python 依赖...\033[0m"
pip3 install --break-system-packages requests > /dev/null 2>&1 || true
echo -e "\033[0;32m✅ 依赖检查完成\033[0m"

# 创建知识提取器脚本
echo -e "\n\033[0;33m▶ 创建知识提取器 knowledge_extractor.py...\033[0m"

cat > "$INTEL_DIR/knowledge_extractor.py" << 'EOF'
#!/usr/bin/env python3
"""
知识提炼引擎：从种子文件中提取结构化知识，存入 SQLite 图谱。
使用 qwen3.5:4b 模型进行本地推理。
"""

import os
import re
import json
import sqlite3
import hashlib
import subprocess
from datetime import datetime
from typing import List, Dict, Any, Tuple
import requests

# 配置
PROJECT_ROOT = "/home/summer/xuzhi_genesis"
INTEL_DIR = os.path.join(PROJECT_ROOT, "centers/intelligence")
SEEDS_DIR = os.path.join(INTEL_DIR, "seeds")
KNOWLEDGE_DIR = os.path.join(INTEL_DIR, "knowledge")
DB_PATH = os.path.join(KNOWLEDGE_DIR, "knowledge.db")
PROCESSED_LOG = os.path.join(KNOWLEDGE_DIR, "processed_seeds.txt")
OLLAMA_URL = "http://localhost:11435/api/generate"
OLLAMA_MODEL = "qwen3.5:4b"  # 修正为正确的模型

# 种子类型定义（与蓝图一致）
SEED_TYPES = [
    "paradigm_shift", "contradiction", "cross_domain_link",
    "testable_hypothesis", "anomaly", "methodology_innovation",
    "predictive_insight", "meta_cognition", "consensus_break",
    "hidden_connection", "cognitive_tool", "antifragile_point"
]

# ==================== 数据库初始化 ====================

def init_db():
    """初始化 SQLite 知识图谱表"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS entities (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        type TEXT,  -- person, organization, concept, technology
        source TEXT,
        first_seen TIMESTAMP,
        last_seen TIMESTAMP,
        confidence REAL
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS relations (
        id TEXT PRIMARY KEY,
        subject_id TEXT,
        predicate TEXT,
        object_id TEXT,
        source TEXT,
        first_seen TIMESTAMP,
        confidence REAL,
        FOREIGN KEY(subject_id) REFERENCES entities(id),
        FOREIGN KEY(object_id) REFERENCES entities(id)
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS seed_entities (
        seed_file TEXT,
        entity_id TEXT,
        FOREIGN KEY(entity_id) REFERENCES entities(id)
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS seed_types (
        seed_file TEXT PRIMARY KEY,
        seed_type TEXT,
        confidence REAL
    )''')
    
    conn.commit()
    conn.close()
    print("✅ 知识图谱数据库初始化完成")

# ==================== 已处理种子记录 ====================

def get_processed_seeds():
    if not os.path.exists(PROCESSED_LOG):
        return set()
    with open(PROCESSED_LOG, 'r') as f:
        return set(line.strip() for line in f)

def mark_seed_processed(seed_file):
    with open(PROCESSED_LOG, 'a') as f:
        f.write(seed_file + "\n")

# ==================== 调用 Ollama 进行提取 ====================

def extract_with_ollama(text: str) -> Dict[str, Any]:
    """调用本地 qwen3.5:4b 模型提取实体、关系、类型"""
    # 限制输入文本长度，避免超时
    if len(text) > 3000:
        text = text[:3000] + "..."
    
    prompt = f"""
    请从以下文本中提取结构化信息，并以 JSON 格式返回。

    文本：
    {text}

    要求：
    1. 实体：识别出的人名、机构名、概念名、技术名，每个实体包含 name 和 type（person/organization/concept/technology）。
    2. 关系：识别实体之间的语义关系，每条关系包含 subject（实体名）、predicate（关系词）、object（实体名）。
    3. 类型：根据以下分类，判断文本最符合哪种种子类型（返回一个字符串）：
       {', '.join(SEED_TYPES)}
       如果不属于任何类型，返回 "general"。

    只输出 JSON，不要其他解释。
    """
    
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "temperature": 0.1,
        "max_tokens": 1024
    }
    try:
        resp = requests.post(OLLAMA_URL, json=payload, timeout=120)
        resp.raise_for_status()
        result = resp.json()
        response_text = result.get("response", "")
        # 提取 JSON 部分
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())
            # 确保字段存在
            if "entities" not in data:
                data["entities"] = []
            if "relations" not in data:
                data["relations"] = []
            if "type" not in data:
                data["type"] = "general"
            return data
        else:
            print("  警告：无法解析模型输出，返回空数据")
            return {"entities": [], "relations": [], "type": "general"}
    except requests.exceptions.Timeout:
        print("  错误：Ollama 请求超时")
        return {"entities": [], "relations": [], "type": "general"}
    except Exception as e:
        print(f"  错误：Ollama 调用失败 - {e}")
        return {"entities": [], "relations": [], "type": "general"}

# ==================== 知识入库 ====================

def generate_entity_id(name: str) -> str:
    return hashlib.sha256(name.encode()).hexdigest()[:16]

def store_knowledge(seed_file: str, content: str, extracted: Dict[str, Any]):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    now = datetime.now().isoformat()
    
    # 存储种子类型
    seed_type = extracted.get("type", "general")
    confidence = 0.8
    c.execute('''INSERT OR REPLACE INTO seed_types (seed_file, seed_type, confidence)
                  VALUES (?, ?, ?)''', (seed_file, seed_type, confidence))
    
    # 存储实体
    entity_ids = {}
    for ent in extracted.get("entities", []):
        name = ent["name"]
        etype = ent.get("type", "concept")
        eid = generate_entity_id(name)
        entity_ids[name] = eid
        c.execute('SELECT id FROM entities WHERE id = ?', (eid,))
        if c.fetchone():
            c.execute('''UPDATE entities SET last_seen = ? WHERE id = ?''', (now, eid))
        else:
            c.execute('''INSERT INTO entities (id, name, type, source, first_seen, last_seen, confidence)
                          VALUES (?, ?, ?, ?, ?, ?, ?)''',
                      (eid, name, etype, seed_file, now, now, 0.8))
    
    # 存储关系
    for rel in extracted.get("relations", []):
        subj = rel.get("subject", "")
        pred = rel.get("predicate", "")
        obj = rel.get("object", "")
        if subj in entity_ids and obj in entity_ids:
            subj_id = entity_ids[subj]
            obj_id = entity_ids[obj]
            rel_id = hashlib.sha256(f"{subj_id}{pred}{obj_id}".encode()).hexdigest()[:16]
            c.execute('''INSERT OR IGNORE INTO relations (id, subject_id, predicate, object_id, source, first_seen, confidence)
                          VALUES (?, ?, ?, ?, ?, ?, ?)''',
                      (rel_id, subj_id, pred, obj_id, seed_file, now, 0.7))
    
    # 关联种子-实体
    for name, eid in entity_ids.items():
        c.execute('''INSERT OR IGNORE INTO seed_entities (seed_file, entity_id) VALUES (?, ?)''',
                  (seed_file, eid))
    
    conn.commit()
    conn.close()
    print(f"  入库完成: 实体 {len(entity_ids)} 个, 关系 {len(extracted.get('relations', []))} 条")

# ==================== 主流程 ====================

def process_new_seeds():
    processed = get_processed_seeds()
    seed_files = sorted([f for f in os.listdir(SEEDS_DIR) if f.endswith('.md')])
    new_seeds = [f for f in seed_files if f not in processed]
    
    if not new_seeds:
        print("没有新的种子文件需要处理。")
        return
    
    print(f"发现 {len(new_seeds)} 个新种子文件，开始提取知识...")
    for idx, seed_file in enumerate(new_seeds, 1):
        print(f"\n[{idx}/{len(new_seeds)}] 处理 {seed_file}...")
        seed_path = os.path.join(SEEDS_DIR, seed_file)
        with open(seed_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        extracted = extract_with_ollama(content)
        print(f"  提取结果: 类型={extracted.get('type','unknown')}, "
              f"实体数={len(extracted.get('entities',[]))}, "
              f"关系数={len(extracted.get('relations',[]))}")
        
        store_knowledge(seed_file, content, extracted)
        mark_seed_processed(seed_file)
    
    print(f"\n✅ 知识提取完成，共处理 {len(new_seeds)} 个文件。")

def main():
    init_db()
    process_new_seeds()

if __name__ == "__main__":
    main()
EOF

chmod +x "$INTEL_DIR/knowledge_extractor.py"
echo -e "\033[0;32m✅ 知识提取器创建成功（使用 qwen3.5:4b）\033[0m"

# 创建查询工具（与之前相同）
cat > "$INTEL_DIR/query_knowledge.py" << 'EOF'
#!/usr/bin/env python3
"""
知识图谱查询工具
"""

import sqlite3
import sys
import os

DB_PATH = "/home/summer/xuzhi_genesis/centers/intelligence/knowledge/knowledge.db"

def print_help():
    print("用法:")
    print("  python query_knowledge.py list-entities            # 列出所有实体")
    print("  python query_knowledge.py entity <name>            # 查询指定实体")
    print("  python query_knowledge.py relations <entity>       # 查询与实体相关的关系")
    print("  python query_knowledge.py type <seed_type>         # 查询指定类型的种子")

def list_entities():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT name, type, confidence FROM entities ORDER BY last_seen DESC LIMIT 20")
    rows = c.fetchall()
    print("最近20个实体：")
    for name, etype, conf in rows:
        print(f"  {name} ({etype}) conf={conf:.2f}")
    conn.close()

def query_entity(name):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, type, source, first_seen, last_seen, confidence FROM entities WHERE name LIKE ?", (f"%{name}%",))
    rows = c.fetchall()
    if not rows:
        print(f"未找到实体 '{name}'")
    else:
        for eid, etype, src, first, last, conf in rows:
            print(f"实体: {name} (ID: {eid})")
            print(f"  类型: {etype}")
            print(f"  首次出现: {first}")
            print(f"  最近出现: {last}")
            print(f"  置信度: {conf}")
            print(f"  来源种子: {src}")
    conn.close()

def query_relations(entity):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id FROM entities WHERE name LIKE ?", (f"%{entity}%",))
    row = c.fetchone()
    if not row:
        print(f"未找到实体 '{entity}'")
        return
    eid = row[0]
    # 主语
    c.execute('''
        SELECT r.predicate, e2.name, r.confidence
        FROM relations r
        JOIN entities e2 ON r.object_id = e2.id
        WHERE r.subject_id = ?
    ''', (eid,))
    rows = c.fetchall()
    print(f"实体 '{entity}' 作为主语的关系：")
    for pred, obj, conf in rows:
        print(f"  -> {pred} -> {obj} (conf={conf:.2f})")
    # 宾语
    c.execute('''
        SELECT e1.name, r.predicate, r.confidence
        FROM relations r
        JOIN entities e1 ON r.subject_id = e1.id
        WHERE r.object_id = ?
    ''', (eid,))
    rows = c.fetchall()
    print(f"实体 '{entity}' 作为宾语的关系：")
    for sub, pred, conf in rows:
        print(f"  {sub} -> {pred} -> (conf={conf:.2f})")
    conn.close()

def query_by_type(seed_type):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        SELECT seed_file, confidence FROM seed_types
        WHERE seed_type = ?
        ORDER BY confidence DESC
        LIMIT 10
    ''', (seed_type,))
    rows = c.fetchall()
    if not rows:
        print(f"未找到类型 '{seed_type}' 的种子")
    else:
        print(f"类型 '{seed_type}' 的种子示例：")
        for fname, conf in rows:
            print(f"  {fname} (conf={conf:.2f})")
    conn.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print_help()
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "list-entities":
        list_entities()
    elif cmd == "entity" and len(sys.argv) > 2:
        query_entity(sys.argv[2])
    elif cmd == "relations" and len(sys.argv) > 2:
        query_relations(sys.argv[2])
    elif cmd == "type" and len(sys.argv) > 2:
        query_by_type(sys.argv[2])
    else:
        print_help()
EOF

chmod +x "$INTEL_DIR/query_knowledge.py"
echo -e "\033[0;32m✅ 查询工具创建成功\033[0m"

# 立即运行一次测试
echo -e "\n\033[0;33m▶ 运行知识提取测试...\033[0m"
python3 "$INTEL_DIR/knowledge_extractor.py"

# 列出最近实体验证
echo -e "\n\033[0;33m▶ 验证知识图谱（最近实体）...\033[0m"
python3 "$INTEL_DIR/query_knowledge.py" list-entities

echo -e "\n\033[0;32m========================================\033[0m"
echo -e "\033[0;32m✅ 知识提炼引擎部署完成！\033[0m"
echo -e "\033[0;32m========================================\033[0m"
echo -e "📁 知识图谱数据库: $KNOWLEDGE_DIR/knowledge.db"
echo -e "📁 提取器脚本: $INTEL_DIR/knowledge_extractor.py"
echo -e "📁 查询工具: $INTEL_DIR/query_knowledge.py"
echo -e ""
echo -e "后续可集成到周期引擎中（可选）："
echo -e "  在 cycle_engine.sh 中添加："
echo -e "    python3 $INTEL_DIR/knowledge_extractor.py"
