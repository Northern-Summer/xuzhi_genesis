#!/bin/bash
#
# enhance_knowledge_engine.sh - 增强知识提取器：支持 verbose 模式 + 周期引擎集成
#

set -e

PROJECT_ROOT="/home/summer/xuzhi_genesis"
INTEL_DIR="$PROJECT_ROOT/centers/intelligence"
CYCLE_ENGINE="$PROJECT_ROOT/centers/engineering/cycle_engine.sh"
BACKUP_DIR="$PROJECT_ROOT/backups/knowledge_enhance_$(date +%Y%m%d%H%M%S)"

echo -e "\033[0;34m========================================\033[0m"
echo -e "\033[0;34m  增强知识提取器：前台可见 + 周期集成\033[0m"
echo -e "\033[0;34m========================================\033[0m\n"

# 备份原脚本
mkdir -p "$BACKUP_DIR"
cp "$INTEL_DIR/knowledge_extractor.py" "$BACKUP_DIR/" 2>/dev/null || true
echo -e "\033[0;32m✅ 已备份原提取器\033[0m"

# 重写知识提取器，增加 verbose 模式和重试逻辑
cat > "$INTEL_DIR/knowledge_extractor.py" << 'EOF'
#!/usr/bin/env python3
"""
知识提炼引擎（增强版）：支持 --verbose 参数实时显示进度，自动重试超时任务。
"""

import os
import re
import json
import sqlite3
import hashlib
import time
from datetime import datetime
from typing import List, Dict, Any, Tuple
import requests
import sys

# 配置
PROJECT_ROOT = "/home/summer/xuzhi_genesis"
INTEL_DIR = os.path.join(PROJECT_ROOT, "centers/intelligence")
SEEDS_DIR = os.path.join(INTEL_DIR, "seeds")
KNOWLEDGE_DIR = os.path.join(INTEL_DIR, "knowledge")
DB_PATH = os.path.join(KNOWLEDGE_DIR, "knowledge.db")
PROCESSED_LOG = os.path.join(KNOWLEDGE_DIR, "processed_seeds.txt")
OLLAMA_URL = "http://localhost:11435/api/generate"
OLLAMA_MODEL = "qwen3.5:4b"

SEED_TYPES = [
    "paradigm_shift", "contradiction", "cross_domain_link",
    "testable_hypothesis", "anomaly", "methodology_innovation",
    "predictive_insight", "meta_cognition", "consensus_break",
    "hidden_connection", "cognitive_tool", "antifragile_point"
]

# 全局 verbose 标志
VERBOSE = False

def vprint(*args, **kwargs):
    if VERBOSE:
        print(*args, **kwargs, flush=True)

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS entities (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        type TEXT,
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
    vprint("✅ 知识图谱数据库初始化完成")

def get_processed_seeds():
    if not os.path.exists(PROCESSED_LOG):
        return set()
    with open(PROCESSED_LOG, 'r') as f:
        return set(line.strip() for line in f)

def mark_seed_processed(seed_file):
    with open(PROCESSED_LOG, 'a') as f:
        f.write(seed_file + "\n")

def extract_with_ollama(text: str, retry=1) -> Dict[str, Any]:
    # 限制文本长度
    if len(text) > 2000:
        text = text[:2000] + "..."
    
    prompt = f"""
    从以下文本中提取结构化信息，以 JSON 格式返回。

    文本：
    {text}

    要求：
    1. 实体：name 和 type（person/organization/concept/technology）。
    2. 关系：每条包含 subject, predicate, object。
    3. 类型：从 {', '.join(SEED_TYPES)} 中选择，否则返回 "general"。

    只输出 JSON，不要解释。
    """
    
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "temperature": 0.1,
        "max_tokens": 1024
    }
    
    for attempt in range(retry + 1):
        try:
            vprint(f"  调用 Ollama（尝试 {attempt+1}/{retry+1}）...")
            resp = requests.post(OLLAMA_URL, json=payload, timeout=120)
            resp.raise_for_status()
            result = resp.json()
            response_text = result.get("response", "")
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                data.setdefault("entities", [])
                data.setdefault("relations", [])
                data.setdefault("type", "general")
                return data
            else:
                vprint("  警告：无法解析模型输出，返回空数据")
                return {"entities": [], "relations": [], "type": "general"}
        except requests.exceptions.Timeout:
            vprint(f"  超时，准备重试...")
            time.sleep(3)
        except Exception as e:
            vprint(f"  错误：{e}")
            if attempt < retry:
                time.sleep(3)
            else:
                return {"entities": [], "relations": [], "type": "general"}
    return {"entities": [], "relations": [], "type": "general"}

def generate_entity_id(name: str) -> str:
    return hashlib.sha256(name.encode()).hexdigest()[:16]

def store_knowledge(seed_file: str, content: str, extracted: Dict[str, Any]):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    now = datetime.now().isoformat()
    
    seed_type = extracted.get("type", "general")
    c.execute('''INSERT OR REPLACE INTO seed_types (seed_file, seed_type, confidence)
                  VALUES (?, ?, ?)''', (seed_file, seed_type, 0.8))
    
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
    
    for name, eid in entity_ids.items():
        c.execute('''INSERT OR IGNORE INTO seed_entities (seed_file, entity_id) VALUES (?, ?)''',
                  (seed_file, eid))
    
    conn.commit()
    conn.close()
    vprint(f"  入库完成: 实体 {len(entity_ids)} 个, 关系 {len(extracted.get('relations', []))} 条")

def process_new_seeds():
    processed = get_processed_seeds()
    seed_files = sorted([f for f in os.listdir(SEEDS_DIR) if f.endswith('.md')])
    new_seeds = [f for f in seed_files if f not in processed]
    
    if not new_seeds:
        print("没有新的种子文件需要处理。" if not VERBOSE else "ℹ️ 没有新种子")
        return
    
    print(f"发现 {len(new_seeds)} 个新种子文件，开始提取知识...")
    for idx, seed_file in enumerate(new_seeds, 1):
        print(f"\n[{idx}/{len(new_seeds)}] 处理 {seed_file}...")
        seed_path = os.path.join(SEEDS_DIR, seed_file)
        with open(seed_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        extracted = extract_with_ollama(content, retry=1)  # 允许重试1次
        print(f"  提取结果: 类型={extracted.get('type','unknown')}, "
              f"实体数={len(extracted.get('entities',[]))}, "
              f"关系数={len(extracted.get('relations',[]))}")
        
        store_knowledge(seed_file, content, extracted)
        mark_seed_processed(seed_file)
    
    print(f"\n✅ 知识提取完成，共处理 {len(new_seeds)} 个文件。")

def main():
    global VERBOSE
    if "--verbose" in sys.argv or "-v" in sys.argv:
        VERBOSE = True
    
    init_db()
    process_new_seeds()

if __name__ == "__main__":
    main()
EOF

chmod +x "$INTEL_DIR/knowledge_extractor.py"
echo -e "\033[0;32m✅ 提取器已增强：支持 --verbose 参数，超时重试\033[0m"

# 集成到周期引擎
echo -e "\n\033[0;33m▶ 将知识提取器加入周期引擎...\033[0m"
if [ -f "$CYCLE_ENGINE" ]; then
    # 备份
    cp "$CYCLE_ENGINE" "$CYCLE_ENGINE.bak.$DATE_TAG"
    
    # 插入静默调用（在 exit 前）
    INSERT_CODE="# Intelligence Center knowledge extraction (run after seeds collection)\nif [ -x $INTEL_DIR/knowledge_extractor.py ]; then\n    $INTEL_DIR/knowledge_extractor.py >> $INTEL_DIR/knowledge.log 2>&1 &\nfi\n"
    
    if grep -q "knowledge_extractor.py" "$CYCLE_ENGINE"; then
        echo -e "\033[0;33m⚠️  知识提取器调用已存在，跳过\033[0m"
    else
        if grep -q "^exit" "$CYCLE_ENGINE"; then
            sed -i "/^exit/i\\$INSERT_CODE" "$CYCLE_ENGINE"
            echo -e "\033[0;32m✅ 已在 exit 前插入知识提取器调用\033[0m"
        else
            echo -e "\n$INSERT_CODE" >> "$CYCLE_ENGINE"
            echo -e "\033[0;32m✅ 已追加知识提取器调用到文件末尾\033[0m"
        fi
    fi
else
    echo -e "\033[0;31m❌ cycle_engine.sh 不存在，请手动集成\033[0m"
fi

# 创建日志文件（确保存在）
touch "$INTEL_DIR/knowledge.log"

echo -e "\n\033[0;33m▶ 运行一次测试（带 verbose）以验证...\033[0m"
python3 "$INTEL_DIR/knowledge_extractor.py" --verbose

echo -e "\n\033[0;32m========================================\033[0m"
echo -e "\033[0;32m✅ 增强完成！\033[0m"
echo -e "\033[0;32m========================================\033[0m"
echo -e "现在您可以使用："
echo -e "  python3 $INTEL_DIR/knowledge_extractor.py --verbose   # 前台运行，实时查看进度"
echo -e "  tail -f $INTEL_DIR/knowledge.log                      # 查看后台运行日志"
echo -e "知识提取器已加入周期引擎，每次周期结束后自动运行（静默模式）。"
