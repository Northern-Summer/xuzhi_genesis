#!/bin/bash
#
# evolve_intelligence_stage1.sh - 情报中心第一阶段进化：动态源管理与星座轮转
# 用法: ./evolve_intelligence_stage1.sh
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
BACKUP_DIR="$PROJECT_ROOT/backups/intelligence_stage1_$(date +%Y%m%d%H%M%S)"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  情报中心第一阶段进化：动态源管理${NC}"
echo -e "${BLUE}========================================${NC}\n"

# --- 1. 备份现有文件 ---
echo -e "${YELLOW}🔄 备份当前情报中心文件...${NC}"
mkdir -p "$BACKUP_DIR"
cp "$INTEL_DIR/seed_collector.py" "$BACKUP_DIR/" 2>/dev/null || true
cp "$CONFIG_DIR"/sources_*.json "$BACKUP_DIR/" 2>/dev/null || true
echo -e "${GREEN}✅ 已备份至: $BACKUP_DIR${NC}"

# --- 2. 初始化源质量数据库 ---
echo -e "\n${YELLOW}🔄 初始化源质量数据库...${NC}"
QUALITY_FILE="$CONFIG_DIR/source_quality.json"

# 如果已存在，先备份再新建
if [ -f "$QUALITY_FILE" ]; then
    cp "$QUALITY_FILE" "$BACKUP_DIR/source_quality.json.bak"
fi

# 写入基础质量数据（从当前脚本中的源列表提取）
cat > "$QUALITY_FILE" << 'EOF'
{
  "sources": [
    {"name": "arXiv_AI", "url": "https://arxiv.org/rss/cs.AI", "tier": "A", "health_score": 1.0, "contribution_score": 0.0, "attempts": 0, "successes": 0, "last_status": "unknown"},
    {"name": "Nature", "url": "https://www.nature.com/nature.rss", "tier": "A", "health_score": 1.0, "contribution_score": 0.0, "attempts": 0, "successes": 0, "last_status": "unknown"},
    {"name": "Quanta", "url": "https://www.quantamagazine.org/feed", "tier": "A", "health_score": 1.0, "contribution_score": 0.0, "attempts": 0, "successes": 0, "last_status": "unknown"},
    {"name": "Edge", "url": "https://www.edge.org/feed", "tier": "A", "health_score": 1.0, "contribution_score": 0.0, "attempts": 0, "successes": 0, "last_status": "unknown"},
    {"name": "Science", "url": "https://www.science.org/feed/rss", "tier": "A", "health_score": 1.0, "contribution_score": 0.0, "attempts": 0, "successes": 0, "last_status": "unknown"},
    {"name": "Wired", "url": "https://www.wired.com/feed/rss", "tier": "B", "health_score": 1.0, "contribution_score": 0.0, "attempts": 0, "successes": 0, "last_status": "unknown"},
    {"name": "TechCrunch", "url": "http://feeds.feedburner.com/TechCrunch", "tier": "B", "health_score": 1.0, "contribution_score": 0.0, "attempts": 0, "successes": 0, "last_status": "unknown"},
    {"name": "TheVerge", "url": "https://www.theverge.com/rss/index.xml", "tier": "B", "health_score": 1.0, "contribution_score": 0.0, "attempts": 0, "successes": 0, "last_status": "unknown"},
    {"name": "Bloomberg", "url": "https://feeds.bloomberg.com/markets/news.rss", "tier": "B", "health_score": 1.0, "contribution_score": 0.0, "attempts": 0, "successes": 0, "last_status": "unknown"},
    {"name": "NYTimes", "url": "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml", "tier": "B", "health_score": 1.0, "contribution_score": 0.0, "attempts": 0, "successes": 0, "last_status": "unknown"},
    {"name": "BBC", "url": "https://feeds.bbci.co.uk/news/rss.xml", "tier": "B", "health_score": 1.0, "contribution_score": 0.0, "attempts": 0, "successes": 0, "last_status": "unknown"},
    {"name": "Economist", "url": "https://www.economist.com/feeds/print-sections/77/business.xml", "tier": "A", "health_score": 1.0, "contribution_score": 0.0, "attempts": 0, "successes": 0, "last_status": "unknown"},
    {"name": "MIT_TechnologyReview", "url": "https://www.technologyreview.com/feed", "tier": "A", "health_score": 1.0, "contribution_score": 0.0, "attempts": 0, "successes": 0, "last_status": "unknown"},
    {"name": "OxfordAcademic", "url": "https://academic.oup.com/rss", "tier": "A", "health_score": 1.0, "contribution_score": 0.0, "attempts": 0, "successes": 0, "last_status": "unknown"},
    {"name": "PNAS", "url": "https://www.pnas.org/rss", "tier": "A", "health_score": 1.0, "contribution_score": 0.0, "attempts": 0, "successes": 0, "last_status": "unknown"}
  ],
  "config": {
    "core_guaranteed_count": 3,
    "max_sources_per_cycle": 10,
    "health_decay": 0.95,
    "success_bonus": 0.1,
    "failure_penalty": 0.2,
    "contribution_weight": 0.3
  }
}
EOF
echo -e "${GREEN}✅ 源质量数据库初始化完成: $QUALITY_FILE${NC}"

# --- 3. 升级采集器脚本 ---
echo -e "\n${YELLOW}🔄 升级采集器脚本，加入动态源管理...${NC}"
COLLECTOR_SCRIPT="$INTEL_DIR/seed_collector.py"

# 写入新版本（内嵌 Python 代码）
cat > "$COLLECTOR_SCRIPT" << 'EOF'
#!/usr/bin/env python3
"""
虚质情报中心 - 动态种子采集器 (进化版·源质量驱动)
每个硬件周期自动运行，基于源质量动态选择“星座”。
"""

import feedparser
import os
import re
import json
import random
import time
from datetime import datetime
from typing import List, Dict, Any
import requests

# ==================== 配置区域 ====================
OUTPUT_DIR = "/home/summer/xuzhi_genesis/centers/intelligence/seeds"
CONFIG_DIR = "/home/summer/xuzhi_genesis/centers/intelligence/config"
QUALITY_FILE = os.path.join(CONFIG_DIR, "source_quality.json")

# 每个源最多取多少条最新条目
MAX_PER_SOURCE = 5
MAX_SUMMARY_LEN = 400
REQUEST_TIMEOUT = 15

# ==================== 源质量数据库操作 ====================

def load_source_quality():
    """加载源质量数据库"""
    with open(QUALITY_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_source_quality(data):
    """保存源质量数据库"""
    # 先备份再写入
    backup = QUALITY_FILE + ".bak"
    if os.path.exists(QUALITY_FILE):
        os.rename(QUALITY_FILE, backup)
    with open(QUALITY_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def update_source_status(name, success, response_time=None, entry_count=0):
    """更新单个源的状态"""
    data = load_source_quality()
    for src in data["sources"]:
        if src["name"] == name:
            src["attempts"] += 1
            if success:
                src["successes"] += 1
                src["last_status"] = "success"
                # 健康分：成功增加，并考虑响应时间（越快加分越多）
                time_bonus = max(0, 1.0 - (response_time / 30)) if response_time else 0.5
                src["health_score"] = min(1.0, src["health_score"] + data["config"]["success_bonus"] + time_bonus*0.1)
                # 贡献分：基于产出条目数
                src["contribution_score"] = src["contribution_score"] * 0.9 + (entry_count / 10)  # 移动平均
            else:
                src["last_status"] = "failure"
                src["health_score"] = max(0.1, src["health_score"] - data["config"]["failure_penalty"])
            break
    save_source_quality(data)

def select_sources_for_cycle():
    """根据质量评分选择本轮抓取的源（星座轮转）"""
    data = load_source_quality()
    config = data["config"]
    sources = data["sources"]
    
    # 计算综合评分 = 健康分 + 贡献分 * 权重
    for s in sources:
        s["score"] = s["health_score"] + config["contribution_weight"] * s["contribution_score"]
    
    # 按评分排序
    sources_sorted = sorted(sources, key=lambda x: x["score"], reverse=True)
    
    # 保证核心源（tier A）中至少有 config["core_guaranteed_count"] 个被选入
    tier_a = [s for s in sources_sorted if s["tier"] == "A"]
    guaranteed = tier_a[:config["core_guaranteed_count"]]
    
    # 剩余名额从所有源中按评分加权随机抽取（避免总是同一批）
    remaining_slots = config["max_sources_per_cycle"] - len(guaranteed)
    if remaining_slots > 0:
        # 从所有源中排除已选中的，按评分作为权重随机选择
        candidates = [s for s in sources if s not in guaranteed]
        weights = [s["score"] for s in candidates]
        # 归一化权重
        total = sum(weights)
        if total > 0:
            weights = [w/total for w in weights]
            chosen_indices = random.choices(range(len(candidates)), weights=weights, k=min(remaining_slots, len(candidates)))
            chosen = [candidates[i] for i in chosen_indices]
        else:
            chosen = random.sample(candidates, min(remaining_slots, len(candidates)))
    else:
        chosen = []
    
    cycle_sources = guaranteed + chosen
    # 打乱顺序
    random.shuffle(cycle_sources)
    
    # 记录选择
    record = {
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "guaranteed": [s["name"] for s in guaranteed],
        "chosen": [s["name"] for s in chosen],
        "all": [s["name"] for s in cycle_sources]
    }
    record_path = os.path.join(CONFIG_DIR, f"cycle_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    with open(record_path, 'w', encoding='utf-8') as f:
        json.dump(record, f, indent=2)
    
    return cycle_sources

# ==================== 抓取与解析 ====================

def fetch_feed(source):
    """抓取 RSS，更新源状态"""
    url = source["url"]
    name = source["name"]
    print(f"开始抓取: {name} ({url})")
    start_time = time.time()
    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        elapsed = time.time() - start_time
        feed = feedparser.parse(resp.text)
        entries = feed.entries
        count = len(entries)
        print(f"完成抓取: {name} (获取到 {count} 条, 耗时 {elapsed:.1f}s)")
        update_source_status(name, success=True, response_time=elapsed, entry_count=count)
        return entries
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"抓取失败 {name} ({type(e).__name__}): {e}")
        update_source_status(name, success=False, response_time=elapsed)
        return []

def clean_text(text):
    if not text:
        return ""
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def extract_core_idea(text):
    sentences = re.split(r'[。！？.!?]', text)
    core = '。'.join(sentences[:3]) if sentences else text
    if len(core) > MAX_SUMMARY_LEN:
        core = core[:MAX_SUMMARY_LEN] + "…"
    return core

def generate_summary(entry):
    title = clean_text(entry.get('title', '无标题'))
    summary = entry.get('summary', '')
    if not summary and 'content' in entry and entry.content:
        content = entry.content[0].value if entry.content else ''
        summary = clean_text(content)
    else:
        summary = clean_text(summary)
    core_idea = extract_core_idea(summary)
    return f"**{title}**\n\n{core_idea}\n\n"

# ==================== 主流程 ====================

def generate_cycle_file():
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H%M%S")
    filename = f"{date_str}_{time_str}_seeds.md"
    filepath = os.path.join(OUTPUT_DIR, filename)
    
    sources = select_sources_for_cycle()
    
    lines = []
    lines.append(f"# 心智种子 - {date_str} {time_str}\n")
    lines.append(f"生成时间：{now.strftime('%Y-%m-%d %H:%M:%S')}\n")
    lines.append(f"本次源：{', '.join([s['name'] for s in sources])}\n")
    lines.append("---\n")
    
    total_entries = 0
    all_summaries = []
    
    for source in sources:
        entries = fetch_feed(source)
        count = 0
        source_lines = [f"## {source['name']} (层级{source.get('tier','C')})\n"]
        for entry in entries[:MAX_PER_SOURCE]:
            summary = generate_summary(entry)
            if summary.strip():
                source_lines.append(f"**原文链接**: {entry.get('link', '无')}\n")
                source_lines.append(summary)
                source_lines.append("---\n")
                count += 1
                total_entries += 1
                all_summaries.append({
                    "source": source['name'],
                    "title": entry.get('title', ''),
                    "link": entry.get('link', '')
                })
        if count == 0:
            source_lines.append("无新条目\n---\n")
        lines.extend(source_lines)
        print(f"  - {source['name']} 贡献 {count} 条")
    
    lines.append(f"\n## 本次收录总览\n")
    lines.append(f"共收录 {total_entries} 条种子，来自 {len(sources)} 个源\n")
    lines.append("### 来源分布\n")
    for summary in all_summaries:
        lines.append(f"- [{summary['source']}] {summary['title']} ([链接]({summary['link']}))\n")
    
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.writelines(lines)
    
    print(f"✅ 种子文件已生成: {filepath}")
    return filepath

def main():
    os.makedirs(CONFIG_DIR, exist_ok=True)
    generate_cycle_file()

if __name__ == "__main__":
    main()
EOF

chmod +x "$COLLECTOR_SCRIPT"
echo -e "${GREEN}✅ 采集器脚本升级完成${NC}"

# --- 4. 立即运行一次测试 ---
echo -e "\n${YELLOW}🔄 立即运行一次测试采集...${NC}"
python3 "$COLLECTOR_SCRIPT"

# --- 5. 完成信息 ---
echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}✅ 情报中心第一阶段进化完成！${NC}"
echo -e "${GREEN}========================================${NC}"
echo -e "📁 源质量数据库: $QUALITY_FILE"
echo -e "📁 采集器脚本: $COLLECTOR_SCRIPT"
echo -e "📁 备份: $BACKUP_DIR"
echo -e ""
echo -e "${BLUE}现在，系统将根据源质量动态选择每日星座。您可以通过以下命令查看源质量变化：${NC}"
echo -e "  cat $QUALITY_FILE | jq .   (需安装 jq)"
echo -e "或直接编辑文件: nano $QUALITY_FILE"
echo -e ""
echo -e "${YELLOW}每次周期运行记录会保存在 $CONFIG_DIR/cycle_*.json 中，可供分析。${NC}"

