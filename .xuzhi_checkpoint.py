#!/usr/bin/env python3
"""
~/.xuzhi_checkpoint.py — checkpoint 读写器
用法:
    python3 ~/.xuzhi_checkpoint.py read        # 读取并显示当前 checkpoint
    python3 ~/.xuzhi_checkpoint.py write       # 从当前系统状态更新 checkpoint
    python3 ~/.xuzhi_checkpoint.py verify       # 验证脚本路径是否正确
    python3 ~/.xuzhi_checkpoint.py diff         # 对比 checkpoint 和实际状态
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone

CHECKPOINT_PATH = "/home/summer/.xuzhi_checkpoint.json"
CRON_SPEC_PATH = "/home/summer/.cron_spec.json"


def utcnow():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def cmd(cmd_str):
    r = subprocess.run(cmd_str, shell=True, capture_output=True, text=True)
    return r.stdout.strip(), r.returncode


def read_checkpoint():
    with open(CHECKPOINT_PATH) as f:
        return json.load(f)


def write_checkpoint(data):
    data["version"] = utcnow()
    with open(CHECKPOINT_PATH, "w") as f:
        json.dump(data, f, indent=2)
    print(f"[{utcnow()}] Checkpoint written: {CHECKPOINT_PATH}")


def cmd_read(args):
    c = read_checkpoint()
    print(f"Checkpoint version: {c['version']}")
    print(f"Gateway: {c['gateway']['status']} at {c['gateway']['url']}")
    print(f"Crons: {len(c['crons'])} defined")
    for cron in c['crons']:
        print(f"  - {cron['name']} ({cron['schedule']})")
    print(f"Scripts:")
    for name, path in c['scripts'].items():
        exists = os.path.exists(path)
        status = "✅" if exists else "❌ MISSING"
        print(f"  {status} {name}: {path}")


def cmd_write(args):
    c = read_checkpoint()

    # 更新 Gateway 状态
    http_code, _ = cmd('curl -s --max-time 3 http://localhost:8765/ -o /dev/null -w "%{http_code}"')
    c["gateway"]["status"] = "alive" if http_code == "200" else f"down({http_code})"

    # 更新 cron 列表（通过 cron tool 查询）
    # 注意：需要通过 openclaw cron list 查询，但这可能在内存中
    # 所以我们依赖 cron_spec + cron_restore.sh 作为真相来源
    c["last_lessons_check"] = utcnow()

    write_checkpoint(c)


def cmd_verify(args):
    c = read_checkpoint()
    errors = []
    for name, path in c["scripts"].items():
        if not os.path.exists(path):
            errors.append(f"  ❌ MISSING: {name} = {path}")

    if errors:
        print("Script verification FAILED:")
        for e in errors:
            print(e)
        return 1
    else:
        print("Script verification PASSED: all paths exist ✅")
        return 0


def cmd_diff(args):
    """对比 checkpoint 和实际 cron 状态"""
    try:
        stdout, _ = cmd("openclaw cron list 2>&1")
        print("Current cron list from Gateway:")
        print(stdout if stdout else "(empty)")
    except Exception as e:
        print(f"Cannot fetch cron list: {e}")
    print("\nExpected crons from checkpoint:")
    c = read_checkpoint()
    for cron in c.get("crons", []):
        print(f"  - {cron['name']} | {cron['schedule']} | {cron['command']}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd_name = sys.argv[1]
    if cmd_name == "read":
        cmd_read(sys.argv[2:])
    elif cmd_name == "write":
        cmd_write(sys.argv[2:])
    elif cmd_name == "verify":
        sys.exit(cmd_verify(sys.argv[2:]))
    elif cmd_name == "diff":
        cmd_diff(sys.argv[2:])
    else:
        print(f"Unknown command: {cmd_name}")
        sys.exit(1)
