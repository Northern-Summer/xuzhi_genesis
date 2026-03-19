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
