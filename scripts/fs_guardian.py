#!/usr/bin/env python3
"""
文件系统守护脚本：每日运行，保持项目整洁
"""
import shutil
import tarfile
from pathlib import Path
from datetime import datetime

ROOT = Path.home() / "xuzhi_genesis"
LOG_DIR = ROOT / "logs"
BACKUP_DIR = ROOT / "backups"
ARCHIVE_SUBDIRS = ["archive/tmp", "archive/scripts"]

def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_DIR / "fs_guardian.log", "a") as f:
        f.write(f"{timestamp} - {msg}\n")

def move_to_archive(path, subdir):
    target_dir = path.parent.parent / subdir
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / path.name
    shutil.move(str(path), str(target))
    log(f"Moved {path} -> {target}")

def main():
    log("=== 开始日常检查 ===")

    # 1. 处理临时文件
    for ext in ["*.bak", "*~"]:
        for f in ROOT.rglob(ext):
            if f.is_file():
                move_to_archive(f, "archive/tmp")

    # 2. 统一日志文件
    for f in ROOT.rglob("*.log"):
        if LOG_DIR not in f.parents:
            target = LOG_DIR / f.name
            if target.exists():
                target = LOG_DIR / f"{f.stem}_{datetime.now().strftime('%Y%m%d%H%M%S')}{f.suffix}"
            shutil.move(str(f), str(target))
            log(f"Moved log {f} -> {target}")

    # 3. 打包备份目录下的子目录
    for item in BACKUP_DIR.iterdir():
        if item.is_dir():
            tar_path = BACKUP_DIR / f"{item.name}.tar.gz"
            with tarfile.open(tar_path, "w:gz") as tar:
                tar.add(item, arcname=item.name)
            shutil.rmtree(item)
            log(f"Packed directory {item} -> {tar_path}")

    # 4. 移动各中心根目录下的演化脚本
    for center in ["intelligence", "mind", "task", "engineering"]:
        center_dir = ROOT / "centers" / center
        if not center_dir.exists():
            continue
        for pattern in ["evolve_*", "deploy_*", "enhance_*"]:
            for f in center_dir.glob(pattern):
                if f.is_file():
                    move_to_archive(f, "archive/scripts")

    # 5. 检查失效软链接
    for f in ROOT.rglob("*"):
        if f.is_symlink() and not f.exists():
            log(f"Broken symlink: {f}")

    log("=== 日常检查完成 ===\n")

if __name__ == "__main__":
    main()
