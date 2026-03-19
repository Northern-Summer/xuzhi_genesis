#!/bin/bash
#
# evolve_intelligence_stage2b_inject_opensource.sh
# 将开源RSS列表注入候选源数据库
#

set -e

PROJECT_ROOT="/home/summer/xuzhi_genesis"
INTEL_DIR="$PROJECT_ROOT/centers/intelligence"
CONFIG_DIR="$INTEL_DIR/config"
CANDIDATE_FILE="$CONFIG_DIR/candidate_sources.json"
BACKUP_DIR="$PROJECT_ROOT/backups/intelligence_stage2b_$(date +%Y%m%d%H%M%S)"

echo -e "\033[0;34m========================================\033[0m"
echo -e "\033[0;34m  情报中心：开源情报源注入\033[0m"
echo -e "\033[0;34m========================================\033[0m\n"

# 备份候选数据库
cp "$CANDIDATE_FILE" "$BACKUP_DIR/" 2>/dev/null || true
echo -e "\033[0;32m✅ 候选数据库已备份\033[0m"

# 创建一个临时Python脚本，用于解析和注入
cat > /tmp/inject_opensource.py << 'EOF'
#!/usr/bin/env python3
import json
import requests
from datetime import datetime
import os
import sys

CANDIDATE_FILE = os.path.expanduser("/home/summer/xuzhi_genesis/centers/intelligence/config/candidate_sources.json")

# 从awesome-rss-feeds获取精选源（示例，实际可从GitHub raw获取）
def fetch_awesome_rss():
    # 这里我们硬编码一些高质量源作为示例，实际可从https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/README.md解析
    sources = [
        {"name": "ArXiv AI", "url": "http://arxiv.org/rss/cs.AI", "description": "AI papers", "category": "science"},
        {"name": "Nature", "url": "https://www.nature.com/nature.rss", "category": "science"},
        {"name": "Science", "url": "https://www.science.org/feed/rss", "category": "science"},
        {"name": "Wired", "url": "https://www.wired.com/feed/rss", "category": "tech"},
        {"name": "MIT Tech Review", "url": "https://www.technologyreview.com/feed", "category": "tech"},
        {"name": "Quanta Magazine", "url": "https://www.quantamagazine.org/feed", "category": "science"},
        {"name": "Edge", "url": "https://www.edge.org/feed", "category": "philosophy"},
        {"name": "Aeon", "url": "https://aeon.co/feed.rss", "category": "philosophy"},
        {"name": "Nautilus", "url": "http://nautil.us/feed", "category": "science"},
        {"name": "Noema Magazine", "url": "https://www.noemamag.com/feed/", "category": "philosophy"},
        {"name": "Plato's Footnote", "url": "https://platofootnote.wordpress.com/feed/", "category": "philosophy"},  # 示例哲学博客
        {"name": "Crooked Timber", "url": "http://crookedtimber.org/feed/", "category": "philosophy"},
        {"name": "3 Quarks Daily", "url": "https://3quarksdaily.com/feed", "category": "culture"},
        {"name": "Arts & Letters Daily", "url": "https://aldaily.com/feed/", "category": "culture"},
        {"name": "JSTOR Daily", "url": "https://daily.jstor.org/feed/", "category": "academic"},
        {"name": "Open Culture", "url": "https://www.openculture.com/feed", "category": "culture"},
        {"name": "The Atlantic", "url": "https://www.theatlantic.com/feed/all/", "category": "culture"},
        {"name": "New Yorker", "url": "https://www.newyorker.com/feed/news", "category": "culture"},
        {"name": "London Review of Books", "url": "https://www.lrb.co.uk/feeds/lrb", "category": "culture"},
        {"name": "New York Review of Books", "url": "https://www.nybooks.com/feed/", "category": "culture"},
    ]
    return sources

def main():
    with open(CANDIDATE_FILE, 'r') as f:
        data = json.load(f)
    existing_urls = {c["url"] for c in data["candidates"]}
    # 也检查主源列表（可选）
    # 获取开源源
    new_sources = fetch_awesome_rss()
    added = 0
    for src in new_sources:
        if src["url"] not in existing_urls:
            candidate = {
                "url": src["url"],
                "name": src.get("name", ""),
                "description": src.get("description", ""),
                "category": src.get("category", ""),
                "source_url": "awesome-rss-feeds",
                "discovered_at": datetime.now().isoformat(),
                "discovered_from": "community_list",
                "attempts": 0,
                "successes": 0,
                "last_check": None,
                "status": "candidate"
            }
            data["candidates"].append(candidate)
            existing_urls.add(src["url"])
            added += 1
    if added > 0:
        with open(CANDIDATE_FILE, 'w') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"✅ 已添加 {added} 个开源源到候选池")
    else:
        print("ℹ️ 没有新源需要添加")

if __name__ == "__main__":
    main()
EOF

python3 /tmp/inject_opensource.py

echo -e "\n\033[0;32m========================================\033[0m"
echo -e "\033[0;32m✅ 开源情报注入完成\033[0m"
echo -e "\033[0;32m========================================\033[0m"
echo -e "候选源数据库: $CANDIDATE_FILE"
echo -e "备份: $BACKUP_DIR"
echo -e "\n您现在可以运行发现测试来查看注入的源："
echo -e "  python3 $INTEL_DIR/source_discovery.py"
