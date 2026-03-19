#!/usr/bin/env python3
"""
文件操作包装器：限制每次调用读写文件数 ≤ 10，并估算 token 数 ≤ 1M。
用法：fs_wrapper.py <agent_id> <action> <file1> [file2 ...]
"""
import sys
import json
import tiktoken
from pathlib import Path
from datetime import datetime

CONFIG_FILE = Path.home() / "xuzhi_genesis/config/context_limits.json"
LOG_FILE = Path.home() / "xuzhi_genesis/logs/context_limiter.log"

def log(level, agent, msg):
    with open(LOG_FILE, 'a') as f:
        f.write(f"[{datetime.now().isoformat()}] {level} {agent}: {msg}\n")

def load_config():
    default = {"max_files": 10, "max_tokens": 1_000_000}
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE) as f:
                cfg = json.load(f)
            return {**default, **cfg}
        except:
            return default
    return default

def estimate_tokens(text, model="cl100k_base"):
    try:
        enc = tiktoken.get_encoding(model)
        return len(enc.encode(text))
    except:
        return len(text) // 4

def main():
    if len(sys.argv) < 4:
        print("用法: fs_wrapper.py <agent_id> <action> <file1> [file2 ...]")
        sys.exit(1)

    agent = sys.argv[1]
    action = sys.argv[2]
    files = sys.argv[3:]
    cfg = load_config()

    # 文件数检查
    if len(files) > cfg["max_files"]:
        msg = f"文件数超限：{len(files)} > {cfg['max_files']}"
        log("REJECT", agent, msg)
        print(f"❌ {msg}")
        sys.exit(1)

    # token 估算
    total_tokens = 0
    details = []
    for f in files:
        p = Path(f)
        if p.is_file():
            try:
                with open(p, 'rb') as fp:
                    raw = fp.read(20000)  # 读前 20KB 估算
                text = raw.decode('utf-8', errors='ignore')
                tokens = estimate_tokens(text)
                total_tokens += tokens
                details.append(f"{p.name}: ~{tokens} tokens")
            except Exception as e:
                log("WARN", agent, f"无法读取 {f}: {e}")

    if total_tokens > cfg["max_tokens"]:
        msg = f"token 超限：{total_tokens} > {cfg['max_tokens']}\n  " + "\n  ".join(details)
        log("REJECT", agent, msg)
        print(f"❌ {msg}")
        sys.exit(1)

    log("ALLOW", agent, f"{action} {len(files)} files, ~{total_tokens} tokens")
    print(f"✅ 允许操作：{action} {len(files)} 个文件 (~{total_tokens} tokens)")

if __name__ == "__main__":
    main()
