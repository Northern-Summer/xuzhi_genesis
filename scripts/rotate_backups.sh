#!/bin/bash
# 备份轮转脚本：保留最近10个备份
BACKUP_DIR="$HOME/xuzhi_genesis/backups"
MAX_BACKUPS=10
cd "$BACKUP_DIR" || exit
ls -t *.tar.gz 2>/dev/null | tail -n +$((MAX_BACKUPS+1)) | while read -r f; do
    echo "$(date): 删除旧备份 $f" >> "$BACKUP_DIR/cleanup.log"
    rm "$f"
done
