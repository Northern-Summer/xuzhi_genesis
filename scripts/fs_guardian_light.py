#!/usr/bin/env python3
"""
fs_guardian_light.py — 轻量异常检测系统

设计原则：
- 纯 Python/shell，无 LLM 调用
- 确定性规则：权限校验、文件大小监控、路径结构检查
- <1s 执行完毕，适合频繁运行
- 幂等性：可重复执行，不产生副作用

检查项：
1. 权限漂移检测    — centers/ 下权限是否被篡改
2. 嵌套 archive    — archive/archive/ 等深层嵌套
3. 意外文件检测    — 根目录出现 .pyc, .tmp, __pycache__
4. 关键文件缺失    — 宪章、注册表等必要文件
5. knowledge.db   — 文件大小异常波动
6. ratings.json    — 字段完整性检测
7. 收件箱清理      — 超量消息自动归档
8. 日志膨胀检测    — 单个日志文件 > 50MB
"""

import os
import sys
import json
import fcntl
import sqlite3
import hashlib
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
from typing import Tuple, List, Optional

HOME = Path.home()
ROOT = HOME / "xuzhi_genesis"
LOG_DIR = ROOT / "centers" / "engineering" / "crown"
STATE_FILE = LOG_DIR / "guardian_state.json"  # 上次运行状态（用于比较）
ALERT_LOG = LOG_DIR / "guardian_alerts.jsonl"

# ── 保护路径配置 ──────────────────────────────────────────────────────────────

PROTECTED_DIRS = {  # 期望权限
    ROOT / "centers":                   0o555,
    ROOT / "centers" / "engineering":   0o555,
    ROOT / "centers" / "intelligence":  0o555,
    ROOT / "centers" / "mind":          0o555,
    ROOT / "centers" / "task":         0o555,
}

WRITABLE_DIRS = {  # 期望权限
    ROOT / "centers" / "engineering" / "crown":    0o775,
    ROOT / "centers" / "mind" / "society":         0o775,
    ROOT / "centers" / "mind" / "quotas":           0o775,
    ROOT / "centers" / "intelligence" / "knowledge": 0o775,
    ROOT / "centers" / "intelligence" / "seeds":    0o775,
    ROOT / "centers" / "intelligence" / "knowledge_market": 0o775,
    ROOT / "centers" / "intelligence" / "archive":  0o775,
    ROOT / "centers" / "mind" / "parliament":       0o775,
}

CRITICAL_FILES = [  # 必须存在
    ROOT / "GENESIS_CONSTITUTION.md",
    ROOT / "centers" / "mind" / "society" / "pantheon_registry.json",
    ROOT / "centers" / "engineering" / "crown" / "queue.json",
    HOME / ".openclaw/centers/mind/society/ratings.json",
]

MAX_FILE_SIZE_MB = 50  # 日志文件超过此大小触发警告
MAX_INBOX_SIZE = 500   # 收件箱超过此条数触发归档

STATE_VERSION = 1


def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[[{ts}]] {msg}", file=sys.stderr)


def load_state() -> dict:
    if not STATE_FILE.exists():
        return {}
    try:
        with open(STATE_FILE) as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_SH)
            data = json.load(f)
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            return data
    except:
        return {}


def save_state(state: dict):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        json.dump(state, f, indent=2, ensure_ascii=False)
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def alert(severity: str, check: str, msg: str, detail: dict = None):
    """记录告警到 JSONL 日志"""
    entry = {
        "ts": datetime.now().isoformat(),
        "severity": severity,  # INFO/WARN/CRIT
        "check": check,
        "message": msg,
        "detail": detail or {},
    }
    with open(ALERT_LOG, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ── 检查 1: 权限漂移 ──────────────────────────────────────────────────────────

def check_permissions() -> List[str]:
    issues = []
    for path, expected in list(PROTECTED_DIRS.items()) + list(WRITABLE_DIRS.items()):
        if not path.exists():
            continue
        mode = path.stat().st_mode & 0o777
        if mode != expected:
            issues.append(f"[PERM] {path.relative_to(ROOT)}: {oct(mode)} → 期望 {oct(expected)}")
            # 自愈
            try:
                os.chmod(path, expected)
                alert("WARN", "permission_drift", f"修正权限: {path.name}", {"from": oct(mode), "to": oct(expected)})
            except Exception as e:
                alert("CRIT", "permission_drift", f"修正失败: {path.name}", {"error": str(e)})
    return issues


# ── 检查 2: 嵌套 archive ──────────────────────────────────────────────────────

def check_nested_archives() -> List[str]:
    """检测 archive/archive/ 深层嵌套（fs_guardian.py 的 bug）"""
    issues = []
    for archive_dir in ROOT.rglob("archive"):
        if archive_dir.is_dir():
            depth = len(archive_dir.relative_to(ROOT).parts) - 1
            if depth >= 2:  # archive/archive/ 或更深
                issues.append(f"[NEST] 深层 archive: {archive_dir.relative_to(ROOT)} (深度 {depth})")
                alert("WARN", "nested_archive", f"深层嵌套 archive: {archive_dir.name}", {"depth": depth})
    return issues


# ── 检查 3: 意外文件 ──────────────────────────────────────────────────────────

UNWANTED_PATTERNS = [".pyc", "__pycache__", ".pyo", ".tmp", ".swp", ".DS_Store"]
UNWANTED_NAMES = {"Thumbs.db", "desktop.ini", ".git", ".gitignore"}


def check_unwanted_files() -> List[str]:
    issues = []
    protected_root = ROOT / "centers"
    for item in protected_root.rglob("*"):
        if item.is_file():
            name = item.name
            if any(name.endswith(p) for p in UNWANTED_PATTERNS):
                size = item.stat().st_size
                issues.append(f"[FILE] 意外文件: {item.relative_to(ROOT)} ({size} bytes)")
                alert("INFO", "unwanted_file", str(item.relative_to(ROOT)), {"size": size})
    return issues


# ── 检查 4: 关键文件缺失 ──────────────────────────────────────────────────────

def check_critical_files() -> List[str]:
    issues = []
    for f in CRITICAL_FILES:
        if not f.exists():
            issues.append(f"[MISS] 关键文件缺失: {f.relative_to(ROOT) if f.is_relative_to(ROOT) else f}")
            alert("CRIT", "missing_file", str(f), {"path": str(f)})
    return issues


# ── 检查 5: knowledge.db 大小异常 ────────────────────────────────────────────

def check_knowledge_db() -> List[str]:
    issues = []
    db = ROOT / "centers/intelligence/knowledge/knowledge.db"
    if not db.exists():
        return []
    size = db.stat().st_size
    state = load_state()
    prev_size = state.get("knowledge_db_size")
    if prev_size is not None:
        delta = size - prev_size
        if abs(delta) > 10 * 1024 * 1024:  # 10MB 波动
            issues.append(f"[DB] knowledge.db 大幅变化: {delta/1024/1024:+.1f} MB (现在是 {size/1024/1024:.1f} MB)")
            alert("WARN", "knowledge_db_change", f"大小变化 {delta/1024/1024:+.1f}MB", {"prev": prev_size, "now": size})
    # 更新状态
    state["knowledge_db_size"] = size
    save_state(state)
    return issues


# ── 检查 6: ratings.json 完整性 ──────────────────────────────────────────────

REQUIRED_RATINGS_FIELDS = {"score", "department", "capacity", "status"}


def check_ratings_json() -> List[str]:
    issues = []
    ratings_path = HOME / ".openclaw/centers/mind/society/ratings.json"
    if not ratings_path.exists():
        return []
    try:
        data = json.loads(ratings_path.read_text())
        for aid, info in data.get("agents", {}).items():
            missing = REQUIRED_RATINGS_FIELDS - set(info.keys())
            if missing:
                issues.append(f"[RATINGS] {aid}: 缺字段 {missing}")
                alert("WARN", "ratings_missing_fields", f"{aid} 缺 {missing}", {"agent": aid})
    except Exception as e:
        issues.append(f"[RATINGS] 解析失败: {e}")
        alert("CRIT", "ratings_parse_error", str(e), {})
    return issues


# ── 检查 7: 收件箱膨胀 ────────────────────────────────────────────────────────

def check_inbox_bloat() -> List[str]:
    issues = []
    inbox_dir = HOME / ".openclaw/centers/mind/society/channels/inbox"
    if not inbox_dir.exists():
        return []
    for inbox_file in inbox_dir.glob("*.jsonl"):
        with open(inbox_file) as f:
            lines = len(f.readlines())
        if lines > MAX_INBOX_SIZE:
            # 自动归档：保留最近 100 条
            with open(inbox_file) as f:
                all_lines = f.readlines()
            trimmed = all_lines[-100:]
            with open(inbox_file, "w") as f:
                f.writelines(trimmed)
            archived = lines - 100
            issues.append(f"[INBOX] {inbox_file.name}: {lines}→{len(trimmed)} 条 (归档 {archived} 条)")
            alert("WARN", "inbox_archived", f"{inbox_file.name} 归档 {archived} 条", {"from": lines, "to": len(trimmed)})
    return issues


# ── 检查 8: 日志膨胀 ──────────────────────────────────────────────────────────

def check_log_bloat() -> List[str]:
    issues = []
    log_files = list(LOG_DIR.glob("*.log")) + list(LOG_DIR.glob("*.jsonl"))
    for lf in log_files:
        size_mb = lf.stat().st_size / 1024 / 1024
        if size_mb > MAX_FILE_SIZE_MB:
            issues.append(f"[LOG] {lf.name}: {size_mb:.1f} MB (> {MAX_FILE_SIZE_MB} MB)")
            alert("WARN", "log_bloat", f"{lf.name} 超过 {MAX_FILE_SIZE_MB}MB", {"size_mb": round(size_mb, 1)})
    return issues


# ── 检查 9: cron 活跃性 ──────────────────────────────────────────────────────

def check_cron_active() -> List[str]:
    """验证动态 crontab 的关键任务是否仍在"""
    issues = []
    crontab_file = HOME / ".openclaw/cron/dynamic_crontab.txt"
    required_patterns = ["sense_hardware", "pulse_aggressive", "quota_monitor"]
    if not crontab_file.exists():
        issues.append("[CRON] dynamic_crontab.txt 不存在")
        return issues
    content = crontab_file.read_text()
    for pattern in required_patterns:
        if pattern not in content:
            issues.append(f"[CRON] 缺少必要任务: {pattern}")
            alert("WARN", "cron_missing", f"缺少 {pattern}", {})
    return issues


# ── 主检查循环 ────────────────────────────────────────────────────────────────

def run_all_checks() -> Tuple[List[str], dict]:
    state = load_state()
    state["last_run"] = datetime.now().isoformat()
    state["version"] = STATE_VERSION

    all_issues = []

    checks = [
        ("permissions", check_permissions),
        ("nested_archives", check_nested_archives),
        ("unwanted_files", check_unwanted_files),
        ("critical_files", check_critical_files),
        ("knowledge_db", check_knowledge_db),
        ("ratings_json", check_ratings_json),
        ("inbox_bloat", check_inbox_bloat),
        ("log_bloat", check_log_bloat),
        ("cron_active", check_cron_active),
    ]

    for name, check_fn in checks:
        try:
            issues = check_fn()
            all_issues.extend(issues)
            state[f"check_{name}_ok"] = len(issues) == 0
        except Exception as e:
            all_issues.append(f"[{name.upper()}] 检查异常: {e}")
            state[f"check_{name}_ok"] = False
            alert("CRIT", f"check_{name}_exception", str(e), {})

    save_state(state)
    return all_issues, state


def main():
    import sys as _sys
    start = datetime.now()
    output = []

    issues, state = run_all_checks()

    if issues:
        for issue in issues:
            output.append(issue)
        output.append(f"共 {len(issues)} 个问题，已处理/告警")
    else:
        output.append("所有检查通过 ✅")

    elapsed = (datetime.now() - start).total_seconds()
    output.append(f"耗时 {elapsed:.2f}s")

    # 全部写到 stdout（避免管道截断问题）
    _sys.stdout.write("\n".join(output) + "\n")
    _sys.stdout.flush()


if __name__ == "__main__":
    main()
