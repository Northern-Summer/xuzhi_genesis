#!/bin/bash
# 回滚所有修改
for bak in "/home/summer/xuzhi_genesis/backups/permission_auto_20260319162859"/*.bak; do
    if [ -f "$bak" ]; then
        original_name="$(basename "$bak" .bak)"
        # 尝试在原始位置查找文件（相对路径复杂，简化：搜索常见目录）
        find "" "/home/summer/xuzhi_genesis" -name "$original_name" -type f -exec cp "$bak" {} \; -quit
        echo "恢复: $original_name"
    fi
done
echo "✅ 回滚完成"
