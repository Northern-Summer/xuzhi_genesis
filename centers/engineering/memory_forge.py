#!/usr/bin/env python3
# 工程改进铁律合规 — Ξ | 2026-03-29
# 自问：此操作是否让系统更安全/准确/优雅/高效？答案：YES
"""
记忆压缩与归档 - 从 sessions.json.bak 降维提取
"""
import json
import os
from pathlib import Path
from datetime import datetime

CLAW_ROOT = Path.home() / ".openclaw"
BACKUP_FILE = CLAW_ROOT / "agents/main/sessions/sessions.json.bak"
ARCHIVE_DIR = CLAW_ROOT / "agents/main/workspace/archives"
INDEX_FILE = CLAW_ROOT / "agents/main/workspace/MEMORY_INDEX.md"
LOG_FILE = CLAW_ROOT / "logs" / "memory_forge.log"

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

def forge_memories():
    log("启动")
    if not BACKUP_FILE.exists():
        log(f"跳过：备份文件不存在 {BACKUP_FILE}")
        return

    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

    try:
        data = json.loads(BACKUP_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        log(f"失败：JSON解析错误 {e}")
        return

    raw_str = json.dumps(data, ensure_ascii=False, indent=2)
    chunk_size = 5000
    chunks = [raw_str[i:i+chunk_size] for i in range(0, len(raw_str), chunk_size)]

    lines = ["# 记忆索引\n\n"]
    for idx, chunk in enumerate(chunks):
        name = f"fragment_{idx:03d}.md"
        path = ARCHIVE_DIR / name
        path.write_text(f"--- 碎片 {idx} ---\n\n{chunk}\n", encoding="utf-8")
        lines.append(f"- `{path}` — {chunk[:50].strip()}...\n")

    INDEX_FILE.write_text("".join(lines), encoding="utf-8")
    log(f"完成：生成 {len(chunks)} 个碎片")

if __name__ == "__main__":
    forge_memories()
