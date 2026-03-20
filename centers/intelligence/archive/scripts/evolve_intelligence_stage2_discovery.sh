#!/bin/bash
#
# evolve_intelligence_stage2_discovery.sh - 情报中心第二阶段：源发现引擎
# 用法: ./evolve_intelligence_stage2_discovery.sh
#

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PROJECT_ROOT="/home/summer/xuzhi_genesis"
INTEL_DIR="$PROJECT_ROOT/centers/intelligence"
SEEDS_DIR="$INTEL_DIR/seeds"
CONFIG_DIR="$INTEL_DIR/config"
BACKUP_DIR="$PROJECT_ROOT/backups/intelligence_stage2_$(date +%Y%m%d%H%M%S)"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  情报中心第二阶段：源发现引擎${NC}"
echo -e "${BLUE}========================================${NC}\n"

# --- 1. 备份现有文件 ---
echo -e "${YELLOW}🔄 备份当前情报中心文件...${NC}"
mkdir -p "$BACKUP_DIR"
cp "$INTEL_DIR"/*.py "$BACKUP_DIR/" 2>/dev/null || true
cp "$CONFIG_DIR"/*.json "$BACKUP_DIR/" 2>/dev/null || true
echo -e "${GREEN}✅ 已备份至: $BACKUP_DIR${NC}"

# --- 2. 创建候选源数据库 ---
echo -e "\n${YELLOW}🔄 初始化候选源数据库...${NC}"
CANDIDATE_FILE="$CONFIG_DIR/candidate_sources.json"

cat > "$CANDIDATE_FILE" << 'EOF'
{
  "candidates": [],
  "config": {
    "probe_interval": 3,
    "success_threshold": 3,
    "min_avg_entries": 2,
    "max_candidates": 100
  }
}
EOF
echo -e "${GREEN}✅ 候选源数据库初始化完成: $CANDIDATE_FILE${NC}"

# --- 3. 添加源发现模块 ---
echo -e "\n${YELLOW}🔄 写入源发现模块: $INTEL_DIR/source_discovery.py${NC}"

cat > "$INTEL_DIR/source_discovery.py" << 'EOF'
#!/usr/bin/env python3
"""
虚质情报中心 - 源发现引擎
从已成功抓取的种子页面中提取 RSS 链接，发现新源。
"""

import os
import json
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from datetime import datetime
import time
import logging
from typing import List, Dict, Any

# 配置
CONFIG_DIR = "/home/summer/xuzhi_genesis/centers/intelligence/config"
SEEDS_DIR = "/home/summer/xuzhi_genesis/centers/intelligence/seeds"
CANDIDATE_FILE = os.path.join(CONFIG_DIR, "candidate_sources.json")
QUALITY_FILE = os.path.join(CONFIG_DIR, "source_quality.json")
LOG_FILE = "/home/summer/xuzhi_genesis/centers/intelligence/discovery.log"

# 设置日志
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

REQUEST_TIMEOUT = 10
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

def load_json(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(filepath, data):
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def is_valid_rss_url(url):
    """简单判断是否为可能的 RSS URL"""
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return False
    # 常见的 RSS 路径特征
    path = parsed.path.lower()
    if any(ext in path for ext in ['.rss', '.xml', 'feed', 'atom', 'rss']):
        return True
    return False

def extract_rss_links_from_html(html, base_url):
    """从 HTML 中提取 RSS link 标签"""
    soup = BeautifulSoup(html, 'html.parser')
    links = []
    for link in soup.find_all('link', type=re.compile(r'application/(rss|atom)\+xml')):
        href = link.get('href')
        if href:
            absolute = urljoin(base_url, href)
            links.append(absolute)
    return links

def discover_from_seed_file(seed_file):
    """从单个种子文件中的链接提取新源"""
    with open(seed_file, 'r', encoding='utf-8') as f:
        content = f.read()
    # 提取所有链接（简单正则）
    urls = re.findall(r'\(https?://[^\s\)]+\)', content)
    urls = [u.strip('()') for u in urls]
    discovered = []
    for url in urls:
        if not url.startswith('http'):
            continue
        try:
            resp = requests.get(url, timeout=REQUEST_TIMEOUT, headers={'User-Agent': USER_AGENT})
            resp.raise_for_status()
            html = resp.text
            rss_links = extract_rss_links_from_html(html, url)
            for rss in rss_links:
                if is_valid_rss_url(rss):
                    discovered.append({
                        "url": rss,
                        "source_url": url,
                        "discovered_at": datetime.now().isoformat(),
                        "discovered_from": os.path.basename(seed_file)
                    })
        except Exception as e:
            logging.debug(f"Error fetching {url}: {e}")
        time.sleep(1)  # 礼貌性延迟
    return discovered

def add_candidates(new_candidates):
    """将新发现的源加入候选池（去重）"""
    data = load_json(CANDIDATE_FILE)
    existing_urls = {c["url"] for c in data["candidates"]}
    # 也检查是否已在主源列表中
    quality = load_json(QUALITY_FILE)
    main_urls = {s["url"] for s in quality["sources"]}
    added = 0
    for cand in new_candidates:
        if cand["url"] not in existing_urls and cand["url"] not in main_urls:
            # 初始化试探参数
            cand["attempts"] = 0
            cand["successes"] = 0
            cand["last_check"] = None
            cand["status"] = "candidate"
            data["candidates"].append(cand)
            existing_urls.add(cand["url"])
            added += 1
    if added > 0:
        save_json(CANDIDATE_FILE, data)
        logging.info(f"Added {added} new candidate sources.")
    return added

def main():
    # 获取最新的种子文件（最近一次生成的）
    seed_files = sorted([f for f in os.listdir(SEEDS_DIR) if f.endswith('.md')], reverse=True)
    if not seed_files:
        logging.info("No seed files found.")
        return
    latest = os.path.join(SEEDS_DIR, seed_files[0])
    logging.info(f"Discovering from {latest}")
    discovered = discover_from_seed_file(latest)
    if discovered:
        added = add_candidates(discovered)
        print(f"发现 {len(discovered)} 个候选源，新增 {added} 个。")
    else:
        print("本次未发现新候选源。")

if __name__ == "__main__":
    main()
EOF

chmod +x "$INTEL_DIR/source_discovery.py"
echo -e "${GREEN}✅ 源发现模块创建成功${NC}"

# --- 4. 安装依赖（若缺少 beautifulsoup4）---
echo -e "\n${YELLOW}🔄 检查并安装 Python 依赖: beautifulsoup4${NC}"
if python3 -c "import bs4" 2>/dev/null; then
    echo -e "${GREEN}✅ beautifulsoup4 已安装${NC}"
else
    pip3 install --break-system-packages beautifulsoup4 > /dev/null 2>&1 || {
        echo -e "${RED}❌ beautifulsoup4 安装失败，请手动执行: pip3 install beautifulsoup4${NC}"
        exit 1
    }
    echo -e "${GREEN}✅ beautifulsoup4 安装成功${NC}"
fi

# --- 5. 修改采集器脚本，在完成后触发发现（可选）---
echo -e "\n${YELLOW}🔄 修改 seed_collector.py 以在采集完成后触发发现...${NC}"
COLLECTOR_SCRIPT="$INTEL_DIR/seed_collector.py"

# 在文件末尾的 main() 调用前添加发现触发
if grep -q "source_discovery" "$COLLECTOR_SCRIPT"; then
    echo -e "${YELLOW}⚠️  发现模块已集成，跳过修改${NC}"
else
    # 在 main() 定义之后，调用之前插入
    sed -i '/def main():/a \    # 触发源发现（后台运行，不阻塞）\n    import subprocess\n    subprocess.Popen(["python3", "'"$INTEL_DIR/source_discovery.py"'"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)' "$COLLECTOR_SCRIPT"
    echo -e "${GREEN}✅ 已添加发现触发逻辑${NC}"
fi

# --- 6. 立即运行一次发现测试 ---
echo -e "\n${YELLOW}🔄 立即运行一次源发现测试...${NC}"
python3 "$INTEL_DIR/source_discovery.py"

# --- 7. 完成信息 ---
echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}✅ 情报中心第二阶段部署完成！${NC}"
echo -e "${GREEN}========================================${NC}"
echo -e "📁 候选源数据库: $CANDIDATE_FILE"
echo -e "📁 发现模块: $INTEL_DIR/source_discovery.py"
echo -e "📁 发现日志: $INTEL_DIR/discovery.log"
echo -e "📁 备份: $BACKUP_DIR"
echo -e ""
echo -e "${BLUE}现在，每次种子采集完成后，发现模块会自动运行，从最新种子中提取链接并发现新源。${NC}"
echo -e "${YELLOW}您可以手动运行发现：python3 $INTEL_DIR/source_discovery.py${NC}"
echo -e "${YELLOW}查看候选源：cat $CANDIDATE_FILE | jq .${NC}"
