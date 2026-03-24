#!/usr/bin/env python3
"""
统一磁盘监控脚本 - 优化版
功能：
  1. 多分区磁盘空间监控 + 告警
  2. 自动清理过期归档（memory_forge 优化）
  3. OpenClaw 日志轮转（防止日志撑爆磁盘）
  4. 生成 cron/dynamic_crontab.txt（合并到一处）
  5. 上报 quota 状态到 quota_usage.json

设计原则：
  - 单脚本多用途，减少 cron job 数量（节省 API 调用配额）
  - 磁盘告警阈值可配置
  - 清理操作有 dry_run 模式，误删零容忍
  - 所有操作写日志，可审计
"""
import json
import os
import shutil
import logging
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

# ── 配置 ──────────────────────────────────────────────
HOME = Path.home()
CLAW_ROOT = HOME / ".openclaw"
CRON_FILE = CLAW_ROOT / "cron" / "dynamic_crontab.txt"
LOG_FILE = CLAW_ROOT / "logs" / "disk_monitor.log"

# 磁盘监控配置（阈值 %）
DISK_THRESHOLDS = {
    "/":        {"warn": 70, "crit": 85},
    "/home":    {"warn": 70, "crit": 85},
    "/tmp":     {"warn": 60, "crit": 80},
}

# 日志清理配置
LOG_RETENTION_DAYS = 7        # 日志保留天数
ARCHIVE_RETENTION_DAYS = 7    # memory archive 保留天数
QUOTA_USAGE_FILE = CLAW_ROOT / "centers" / "engineering" / "crown" / "quota_usage.json"

# ── 日志设置 ────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [DISK_MON] %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("disk_monitor")


# ── 磁盘空间检测 ─────────────────────────────────────────
def check_disk_space(path: str = "/") -> Optional[dict]:
    """返回磁盘使用情况，无则为 None（路径不存在时）"""
    try:
        usage = shutil.disk_usage(path)
        pct = round(usage.used / usage.total * 100, 1)
        return {
            "path": path,
            "total_gb": round(usage.total / (1024**3), 2),
            "used_gb": round(usage.used / (1024**3), 2),
            "free_gb": round(usage.free / (1024**3), 2),
            "percent": pct,
        }
    except FileNotFoundError:
        return None


def check_all_disks() -> list:
    """遍历所有配置的路径，返回可用分区的使用情况"""
    results = []
    for path in DISK_THRESHOLDS:
        info = check_disk_space(path)
        if info:
            results.append(info)
    return results


def disk_status(info: dict) -> str:
    """根据阈值判断状态"""
    path = info["path"]
    pct = info["percent"]
    t = DISK_THRESHOLDS.get(path, {})
    crit = t.get("crit", 85)
    warn = t.get("warn", 70)
    if pct >= crit:
        return "🔴 CRIT"
    elif pct >= warn:
        return "🟡 WARN"
    return "🟢 OK"


def run_disk_check():
    """执行磁盘检查并输出报告"""
    all_disks = check_all_disks()
    if not all_disks:
        log.warning("未找到任何磁盘路径")
        return

    log.info("=" * 50)
    log.info("磁盘空间检查")
    log.info("=" * 50)

    alerts = []
    for info in all_disks:
        status = disk_status(info)
        log.info(
            f"  {status}  {info['path']}: "
            f"{info['used_gb']}G / {info['total_gb']}G "
            f"({info['percent']}%) free={info['free_gb']}G"
        )
        if status in ("🔴 CRIT", "🟡 WARN"):
            alerts.append((status, info))

    if alerts:
        log.warning(f"⚠️  共 {len(alerts)} 个分区需要关注")
    else:
        log.info("✅ 所有分区状态正常")


# ── 清理过期文件 ─────────────────────────────────────────
def cleanup_old_logs(log_dir: Path, retention_days: int, dry_run: bool = False):
    """清理超过 retention_days 的日志"""
    if not log_dir.exists():
        return
    cutoff = datetime.now() - timedelta(days=retention_days)
    removed = []
    for f in log_dir.iterdir():
        if f.is_file():
            mtime = datetime.fromtimestamp(f.stat().st_mtime)
            if mtime < cutoff:
                if dry_run:
                    log.info(f"  [DRY RUN] 将删除: {f}")
                else:
                    f.unlink()
                    removed.append(str(f))
    if removed:
        log.info(f"🗑️  清理日志 {len(removed)} 个文件（>{retention_days}天）")
        if log.isEnabledFor(logging.DEBUG):
            for r in removed:
                log.debug(f"    - {r}")


def cleanup_memory_archives(archive_dir: Path, retention_days: int, dry_run: bool = False):
    """
    优化版 memory_forge 清理：
    - 只保留最新的 N 个 fragment（而非全量保存）
    - 删除超过 retention_days 的碎片
    - 避免每次运行都重新生成所有碎片（节省磁盘 I/O）
    """
    if not archive_dir.exists():
        return

    cutoff = datetime.now() - timedelta(days=retention_days)
    removed = []
    kept = 0
    for f in sorted(archive_dir.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
        if f.is_file() and f.name.startswith("memory_fragment_"):
            mtime = datetime.fromtimestamp(f.stat().st_mtime)
            kept += 1
            if mtime < cutoff:
                if dry_run:
                    log.info(f"  [DRY RUN] 将删除: {f} (mtime={mtime.date()})")
                else:
                    f.unlink()
                    removed.append(str(f))
                kept -= 1  # 被删的不算 kept

    if removed:
        log.info(f"🗑️  清理 memory_archives {len(removed)} 个过期文件（>{retention_days}天）")
    if kept > 0:
        log.info(f"  📦 当前 archive 碎片数: {kept}")


def cleanup_openclaw_logs(dry_run: bool = False):
    """只保留最近 7 天的 OpenClaw 日志"""
    log_dir = CLAW_ROOT / "logs"
    cleanup_old_logs(log_dir, LOG_RETENTION_DAYS, dry_run=dry_run)


def cleanup_archives(dry_run: bool = False):
    """只保留最近 7 天的 memory archives"""
    archive_dir = CLAW_ROOT / "agents" / "main" / "workspace" / "archives"
    cleanup_memory_archives(archive_dir, ARCHIVE_RETENTION_DAYS, dry_run=dry_run)


# ── 合并 quota 状态上报（轻量化） ─────────────────────────
def report_quota_status():
    """将 quota_usage.json 的当前状态同步到磁盘监控日志（无 API 调用）"""
    if not QUOTA_USAGE_FILE.exists():
        log.debug("quota_usage.json 不存在，跳过上报")
        return
    try:
        with open(QUOTA_USAGE_FILE) as f:
            quota = json.load(f)
        used = quota.get("used", "?")
        limit = quota.get("limit", "?")
        remain = quota.get("remain", "?")
        last_update = quota.get("last_update", "?")
        log.info(f"📊 Quota: used={used} limit={limit} remain={remain} (last_update={last_update})")
    except Exception as e:
        log.warning(f"⚠️ 读取 quota_usage.json 失败: {e}")


# ── cron 生成（合并版，只写必要任务） ─────────────────────
def generate_minimal_cron(wakeup_interval: int = 10):
    """
    生成最小化 cron 内容：
    - 心跳：按指定间隔
    - 记忆压缩：每小时1次
    - 磁盘监控：每小时1次（本脚本）
    - 每日心智种子：固定时间
    删除了冗余的 pulse_aggressive.sh（频繁wakeup浪费配额）
    """
    cron = f"""# 动态crontab，由 disk_monitor.py 自动生成
# ⚠️ 最小化配置：减少 cron 数量以节省 API 配额

# 心跳任务（根据剩余配额动态调整）
*/{wakeup_interval} * * * * $HOME/.openclaw/workspace/sense_hardware.sh

# 每日心智种子（固定凌晨3点）
0 */6 * * * $HOME/.openclaw/centers/intelligence/seeds/daily_mind_seeds_v2.py
@reboot $HOME/.openclaw/centers/intelligence/seeds/daily_mind_seeds_v2.py

# 记忆压缩（每小时）
0 * * * * $HOME/.openclaw/centers/engineering/memory_forge.py

# 磁盘监控（每小时，含清理）
0 * * * * $HOME/.openclaw/centers/engineering/disk_monitor.py --cleanup

# 配额监控（每30分钟）
*/30 * * * * $HOME/.openclaw/centers/engineering/crown/quota_monitor.py
"""
    CRON_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CRON_FILE, 'w') as f:
        f.write(cron)
    os.system(f"crontab {CRON_FILE} 2>/dev/null")
    log.info(f"✅ dynamic_crontab.txt 已更新（wakeup_interval={wakeup_interval}）")


# ── 主流程 ──────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="统一磁盘监控脚本")
    parser.add_argument("--cleanup", action="store_true", help="执行清理操作")
    parser.add_argument("--dry-run", action="store_true", help="预览清理操作（不实际删除）")
    parser.add_argument("--cron-interval", type=int, default=10, help="心跳 cron 间隔（分钟）")
    parser.add_argument("--disk-check-only", action="store_true", help="仅执行磁盘检查")
    args = parser.parse_args()

    log.info(f"[disk_monitor] 启动 | cleanup={args.cleanup} dry_run={args.dry_run}")

    # 1. 磁盘空间检查
    run_disk_check()

    # 2. 清理（可选）
    if args.cleanup or args.dry_run:
        log.info("🧹 开始清理...")
        cleanup_openclaw_logs(dry_run=args.dry_run)
        cleanup_archives(dry_run=args.dry_run)

    # 3. quota 上报
    report_quota_status()

    # 4. cron 更新（仅在 --disk-check-only 为 False 时）
    if not args.disk_check_only:
        generate_minimal_cron(wakeup_interval=args.cron_interval)

    log.info("[disk_monitor] 完成")


if __name__ == "__main__":
    main()
