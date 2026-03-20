#!/usr/bin/env python3
"""
genesis_probe.py - 极简唤醒探针
设计原则：最小输出 + 缓存失效 + 零冗余
"""
import os
import subprocess
import hashlib
import json
import sys
from pathlib import Path

XUZHI_ROOT = Path.home() / "xuzhi_genesis"
CENTERS = ["mind", "intelligence", "engineering", "task"]
CACHE_FILE = XUZHI_ROOT / "centers/mind/.probe_cache.json"
QUICK_THRESHOLD = 5  # 相同上下文字符串直接输出（秒级防抖）


def run_cmd(cmd: str, cwd: Path = None) -> str:
    try:
        result = subprocess.run(
            cmd, shell=True, cwd=cwd or XUZHI_ROOT,
            capture_output=True, text=True, timeout=10
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except:
        return ""


def get_cache_key() -> dict:
    """计算当前上下文指纹（用于判断是否需要重新生成简报）"""
    # 1. Git 变更哈希
    git_hash = run_cmd("git rev-parse HEAD")
    git_status = run_cmd("git status --short")
    status_hash = hashlib.md5(git_status.encode()).hexdigest()[:8]

    # 2. 各中心核心文件快照（仅计数+最近修改的文件）
    center_meta = {}
    for center in CENTERS:
        cp = XUZHI_ROOT / "centers" / center
        if not cp.exists():
            center_meta[center] = {"count": 0, "files": []}
            continue
        # 过滤备份和隐藏文件
        core = [f.name for f in cp.iterdir() if f.is_file()
                and not (f.name.startswith('.') or '.bak' in f.name)]
        # 取最近3个修改的文件名（按mtime）
        recent = sorted(core, key=lambda f: os.path.getmtime(cp / f),
                        reverse=True)[:3]
        center_meta[center] = {"count": len(core), "recent": recent}

    # 3. 当前任务
    task = {}
    task_file = XUZHI_ROOT / "centers/task/current_task.json"
    if task_file.exists():
        try:
            with open(task_file) as f:
                td = json.load(f)
                task = {"title": td.get("title", ""), "status": td.get("status", "")}
        except:
            pass

    return {
        "git_hash": git_hash,
        "git_status_hash": status_hash,
        "centers": center_meta,
        "task": task,
    }


def get_briefing_text(force: bool = False) -> str:
    """
    生成唤醒简报文本。
    若缓存未失效且非force模式，返回 "[CACHED]"，上层直接跳过输出。
    """
    global CACHE_FILE, QUICK_THRESHOLD

    current_key = get_cache_key()
    current_str = json.dumps(current_key, sort_keys=True)
    current_hash = hashlib.md5(current_str.encode()).hexdigest()

    # 尝试加载缓存
    if not force and CACHE_FILE.exists():
        try:
            with open(CACHE_FILE) as f:
                cache = json.load(f)
            # 缓存命中 & Git HEAD未变
            if (cache.get("hash") == current_hash
                    and cache.get("git_hash") == current_key["git_hash"]):
                return "[CACHED]"  # 快速路径：无需重新生成
        except:
            pass

    # ── 缓存未命中或强制刷新：生成完整简报 ─────────────────────────
    git_status = run_cmd("git status --short")
    important = [l for l in git_status.split('\n') if l
                 and not any(x in l for x in ['.bak', '.tar.gz', '__pycache__'])]

    # 构建拓扑
    topo_parts = []
    for center, meta in current_key["centers"].items():
        label = f"{center}/ [{meta['count']} files]"
        if meta["recent"]:
            label += f" · {', '.join(meta['recent'])}"
        topo_parts.append(label)

    topo = " | ".join(topo_parts) if topo_parts else "No centers found"

    task_title = current_key.get("task", {}).get("title", "N/A")
    task_status = current_key.get("task", {}).get("status", "N/A")

    git_ctx = ""
    if important:
        git_ctx = " | ".join(important)
    else:
        git_ctx = "(clean)"

    # 极简一行摘要（不冗余SOUL.md已载内容）
    briefing = (
        f"[SYS_RESTORE] git={current_key['git_hash'][:7]} | "
        f"status={current_key['git_status_hash']} | "
        f"task=[{task_status}] {task_title} | "
        f"topo={topo} | "
        f"changes={git_ctx}"
    )

    # 写缓存
    try:
        with open(CACHE_FILE, 'w') as f:
            json.dump({"hash": current_hash, "git_hash": current_key["git_hash"],
                       "briefing": briefing}, f, indent=2)
    except:
        pass

    return briefing


if __name__ == "__main__":
    force = "--force" in sys.argv
    result = get_briefing_text(force=force)

    if result == "[CACHED]":
        # 极轻量提示，避免上下文膨胀
        print("[SYS_RESTORE] cached")
    else:
        print(result)
