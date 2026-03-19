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
        SELECT e2.name, r.predicate, r.confidence, r.last_seen
        FROM relations r
        JOIN entities e1 ON r.subject_id = e1.id
        JOIN entities e2 ON r.object_id = e2.id
        WHERE e1.id = ?
    ''', (eid,))
    out_rels = c.fetchall()
    # 查询入向关系
    c.execute('''
        SELECT e1.name, r.predicate, r.confidence, r.last_seen
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
