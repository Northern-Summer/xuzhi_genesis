#!/bin/bash
echo "=== 虚质项目状态快照 ($(date)) ==="
echo ""
echo "## Git 最新提交"
cd "$HOME/xuzhi_genesis" && git log -1 --pretty=format:"%h - %s (%cr)" 2>/dev/null || echo "无Git历史"
echo ""
echo "## 当前标签"
cd "$HOME/xuzhi_genesis" && git tag | tail -5 2>/dev/null || echo "无标签"
echo ""
echo "## 目录树 (关键部分)"
if command -v tree &> /dev/null; then
    tree -L 2 -I '*.pyc|__pycache__|*.log' "$HOME/xuzhi_genesis/centers" 2>/dev/null || echo "tree 命令失败"
else
    echo "tree 未安装，请手动查看目录结构"
fi
echo ""
echo "## 最近修改的文件"
find "$HOME/xuzhi_genesis" -type f -mtime -1 -not -path '*/.git/*' 2>/dev/null | head -20 || echo "无近期修改"
echo ""
echo "## 待办清单 (来自 CONTEXT.md)"
if [ -f "$HOME/xuzhi_genesis/CONTEXT.md" ]; then
    sed -n '/## 待办清单/,/## /p' "$HOME/xuzhi_genesis/CONTEXT.md" | grep -v '## ' | sed '/^$/d' || echo "无待办"
else
    echo "CONTEXT.md 不存在"
fi
echo ""
echo "## 关键数据文件内容"
echo "### departments.json"
if [ -f "$HOME/.openclaw/centers/engineering/crown/departments.json" ]; then
    cat "$HOME/.openclaw/centers/engineering/crown/departments.json"
else
    echo "文件不存在"
fi
echo ""
echo "### ratings.json (摘要)"
if [ -f "$HOME/xuzhi_genesis/centers/mind/society/ratings.json" ]; then
    jq '.agents | map_values({score, capability})' "$HOME/xuzhi_genesis/centers/mind/society/ratings.json" 2>/dev/null || echo "jq 解析失败"
else
    echo "文件不存在"
fi
echo ""
echo "=== 快照结束 ==="
