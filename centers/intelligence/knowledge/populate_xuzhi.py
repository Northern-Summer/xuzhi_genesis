#!/usr/bin/env python3
"""
补全 Xuzhi 系统架构实体和关系
"""
import sqlite3
import uuid
from datetime import datetime, timezone

DB_PATH = "/home/summer/xuzhi_genesis/centers/intelligence/knowledge/knowledge.db"
NOW = datetime.now(timezone.utc).isoformat()

def mkid():
    return str(uuid.uuid4())[:16]

def entity_exists(conn, name):
    c = conn.cursor()
    c.execute("SELECT id FROM entities WHERE name = ?", (name,))
    return c.fetchone()

def insert_entity(conn, eid, name, etype, source="xuzhi-core", confidence=0.95):
    c = conn.cursor()
    c.execute("""
        INSERT OR IGNORE INTO entities (id, name, type, source, first_seen, last_seen, confidence)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (eid, name, etype, source, NOW, NOW, confidence))
    if c.rowcount > 0:
        print(f"  + entity: {name} ({etype})")

def insert_relation(conn, rid, sid, pred, oid, confidence=0.95):
    c = conn.cursor()
    c.execute("""
        INSERT OR IGNORE INTO relations (id, subject_id, predicate, object_id, source, first_seen, last_seen, confidence)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (rid, sid, pred, oid, "xuzhi-core", NOW, NOW, confidence))
    if c.rowcount > 0:
        print(f"  + relation: {pred}")

def main():
    conn = sqlite3.connect(DB_PATH)
    print("=== 补全 Xuzhi 系统架构 ===")

    # ── 实体 ──────────────────────────────────────────
    print("\n[实体]")
    e_xuzhi    = mkid(); insert_entity(conn, e_xuzhi,    "XuzhiSystem",      "concept")
    e_oc       = mkid(); insert_entity(conn, e_oc,       "OpenClaw",         "technology")
    e_lambda   = mkid(); insert_entity(conn, e_lambda,   "LambdaErgo",       "agent")
    e_sci      = mkid(); insert_entity(conn, e_sci,      "Scientist",        "agent")
    e_eng      = mkid(); insert_entity(conn, e_eng,       "Engineer",         "agent")
    e_phil     = mkid(); insert_entity(conn, e_phil,     "Philosopher",      "agent")
    e_kb       = mkid(); insert_entity(conn, e_kb,       "knowledge.db",     "data")
    e_ollama   = mkid(); insert_entity(conn, e_ollama,    "Ollama",           "technology")
    e_rss      = mkid(); insert_entity(conn, e_rss,       "RSS",              "technology")
    e_genesis  = mkid(); insert_entity(conn, e_genesis,   "genesis_probe.py","file")
    e_mind     = mkid(); insert_entity(conn, e_mind,      "centers/mind",    "directory")
    e_intel    = mkid(); insert_entity(conn, e_intel,     "centers/intelligence","directory")
    e_agents   = mkid(); insert_entity(conn, e_agents,   "AGENTS.md",        "file")
    e_memory   = mkid(); insert_entity(conn, e_memory,   "MEMORY.md",        "file")
    e_linux    = mkid(); insert_entity(conn, e_linux,    "Linux",            "technology")
    e_wsl      = mkid(); insert_entity(conn, e_wsl,      "WSL2",             "technology")
    e_rust     = mkid(); insert_entity(conn, e_rust,     "Rust",             "technology")
    e_python   = mkid(); insert_entity(conn, e_python,    "Python",           "technology")
    e_routine   = mkid(); insert_entity(conn, e_routine,  "轮值机制",         "concept")

    # ── 关系 ──────────────────────────────────────────
    print("\n[关系]")

    # 系统结构
    insert_relation(conn, mkid(), e_xuzhi,   "has_component",     e_oc)
    insert_relation(conn, mkid(), e_xuzhi,   "has_component",     e_mind)
    insert_relation(conn, mkid(), e_xuzhi,   "has_component",     e_intel)
    insert_relation(conn, mkid(), e_xuzhi,   "has_component",     e_agents)
    insert_relation(conn, mkid(), e_xuzhi,   "has_component",     e_memory)
    insert_relation(conn, mkid(), e_xuzhi,   "manages",           e_kb)
    insert_relation(conn, mkid(), e_xuzhi,   "uses",              e_ollama)
    insert_relation(conn, mkid(), e_xuzhi,   "has_source",        e_rss)
    insert_relation(conn, mkid(), e_xuzhi,   "runs_on",           e_linux)
    insert_relation(conn, mkid(), e_xuzhi,   "runs_on",           e_wsl)

    # Agent 成员
    insert_relation(conn, mkid(), e_xuzhi,   "has_agent",         e_lambda)
    insert_relation(conn, mkid(), e_xuzhi,   "has_agent",         e_sci)
    insert_relation(conn, mkid(), e_xuzhi,   "has_agent",         e_eng)
    insert_relation(conn, mkid(), e_xuzhi,   "has_agent",         e_phil)

    # 轮值机制
    insert_relation(conn, mkid(), e_routine,  "has_member",        e_lambda)
    insert_relation(conn, mkid(), e_routine,  "has_member",        e_sci)
    insert_relation(conn, mkid(), e_routine,  "has_member",        e_eng)
    insert_relation(conn, mkid(), e_routine,  "has_member",        e_phil)
    insert_relation(conn, mkid(), e_lambda,   "rotation_next",     e_sci)
    insert_relation(conn, mkid(), e_sci,     "rotation_next",     e_eng)
    insert_relation(conn, mkid(), e_eng,      "rotation_next",     e_phil)
    insert_relation(conn, mkid(), e_phil,     "rotation_next",     e_lambda)
    insert_relation(conn, mkid(), e_lambda,   "rotation_score",    e_sci)
    insert_relation(conn, mkid(), e_sci,      "rotation_score",   e_eng)
    insert_relation(conn, mkid(), e_eng,      "rotation_score",   e_phil)
    insert_relation(conn, mkid(), e_phil,    "rotation_score",   e_lambda)

    # 技术栈
    insert_relation(conn, mkid(), e_oc,       "implements",        e_python)
    insert_relation(conn, mkid(), e_oc,       "implemented_in",   e_rust)
    insert_relation(conn, mkid(), e_ollama,   "serves",           e_xuzhi)
    insert_relation(conn, mkid(), e_genesis,  "located_in",       e_mind)
    insert_relation(conn, mkid(), e_mind,     "located_in",       e_xuzhi)
    insert_relation(conn, mkid(), e_intel,   "located_in",       e_xuzhi)
    insert_relation(conn, mkid(), e_kb,      "located_in",       e_intel)

    conn.commit()
    conn.close()
    print("\n✅ 完成")

if __name__ == "__main__":
    main()
