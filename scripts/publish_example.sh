#!/bin/bash
# 示例发布工具 - 展示如何在应用层控制公共空间写入
# 实际使用时应集成到公开发表机制中

AGENT_ID="$1"
ARTIFACT_FILE="$2"

if [ -z "$AGENT_ID" ] || [ -z "$ARTIFACT_FILE" ]; then
    echo "用法: publish_example.sh <agent_id> <file>"
    exit 1
fi

PUBLIC_DIR="$HOME/xuzhi_genesis/public"
RATINGS_FILE="$HOME/.openclaw/centers/mind/society/ratings.json"

# 检查调用者是否为有效 Agent
if ! grep -q "\"$AGENT_ID\"" "$RATINGS_FILE"; then
    echo "错误：无效的 Agent ID"
    exit 1
fi

# 检查文件是否存在
if [ ! -f "$ARTIFACT_FILE" ]; then
    echo "错误：文件不存在"
    exit 1
fi

# 检查 Agent 是否有发表资格（示例：评分≥5）
SCORE=$(python3 -c "
import json
with open('$RATINGS_FILE') as f:
    data = json.load(f)
print(data.get('agents', {}).get('$AGENT_ID', {}).get('score', 0))
")
if [ "$SCORE" -lt 5 ]; then
    echo "错误：社会评价不足，需要≥5分才能发表"
    exit 1
fi

# 复制到公共空间并添加元数据
DEST="$PUBLIC_DIR/$(basename "$ARTIFACT_FILE").$(date +%Y%m%d%H%M%S)"
cp "$ARTIFACT_FILE" "$DEST"
echo "发表时间: $(date)" > "$DEST.meta"
echo "发表者: $AGENT_ID" >> "$DEST.meta"
echo "评分: $SCORE" >> "$DEST.meta"
chmod 644 "$DEST" "$DEST.meta"

echo "✅ 成果已发布到公共空间：$(basename "$DEST")"
