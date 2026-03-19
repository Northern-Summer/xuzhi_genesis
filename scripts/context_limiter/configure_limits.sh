#!/bin/bash
# 查看/修改上下文限制配置
CONFIG_FILE="$HOME/xuzhi_genesis/config/context_limits.json"
if [ ! -f "$CONFIG_FILE" ]; then
    echo '{"max_files": 10, "max_tokens": 1000000}' > "$CONFIG_FILE"
    echo "已创建默认配置"
fi
echo "当前配置:"
cat "$CONFIG_FILE"
echo ""
echo "如需修改，请编辑: $CONFIG_FILE"
