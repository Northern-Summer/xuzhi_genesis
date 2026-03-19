#!/bin/bash
#
# deploy_intelligence.sh - 虚质情报中心第一纪元部署脚本
# 用法: ./deploy_intelligence.sh
#
# 功能：
# 1. 安装依赖 feedparser
# 2. 创建种子采集器脚本 (基于升级版 MVP)
# 3. 配置周期触发 (修改 centers/engineering/cycle_engine.sh)
# 4. 立即运行一次采集验证
#

set -e  # 任何错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 项目根目录
PROJECT_ROOT="/home/summer/xuzhi_genesis"
INTEL_DIR="$PROJECT_ROOT/centers/intelligence"
SEEDS_DIR="$INTEL_DIR/seeds"
CONFIG_DIR="$INTEL_DIR/config"
ENGINEERING_DIR="$PROJECT_ROOT/centers/engineering"
CYCLE_ENGINE="$ENGINEERING_DIR/cycle_engine.sh"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}    虚质情报中心 第一纪元部署脚本${NC}"
echo -e "${BLUE}========================================${NC}\n"

# --- 步骤 1: 备份情报中心目录 ---
BACKUP_DIR="/home/summer/xuzhi_genesis/backups/intelligence_$(date +%Y%m%d%H%M%S)"
echo -e "${YELLOW}🔄 正在备份现有情报中心目录...${NC}"
mkdir -p "$BACKUP_DIR"
if [ -d "$INTEL_DIR" ] && [ "$(ls -A $INTEL_DIR)" ]; then
    cp -r "$INTEL_DIR"/* "$BACKUP_DIR/" 2>/dev/null || true
    echo -e "${GREEN}✅ 已备份至: $BACKUP_DIR${NC}"
else
    echo -e "${YELLOW}⚠️  情报中心目录为空，跳过备份${NC}"
fi

# --- 步骤 2: 安装 Python 依赖 ---
echo -e "\n${YELLOW}🔄 安装 Python 依赖 feedparser...${NC}"
pip3 install feedparser > /dev/null 2>&1 || {
    echo -e "${RED}❌ feedparser 安装失败，请手动安装: pip3 install feedparser${NC}"
    exit 1
}
echo -e "${GREEN}✅ feedparser 安装成功${NC}"

# --- 步骤 3: 创建配置目录 ---
echo -e "\n${YELLOW}🔄 创建配置目录...${NC}"
mkdir -p "$CONFIG_DIR"
mkdir -p "$SEEDS_DIR"
echo -e "${GREEN}✅ 配置目录: $CONFIG_DIR${NC}"
echo -e "${GREEN}✅ 种子存储目录: $SEEDS_DIR${NC}"

# --- 步骤 4: 写入种子采集器脚本 ---
COLLECTOR_SCRIPT="$INTEL_DIR/seed_collector.py"
echo -e "\n${YELLOW}🔄 写入采集器脚本: $COLLECTOR_SCRIPT${NC}"

cat > "$COLLECTOR_SCRIPT" << 'EOF'
#!/usr/bin/env python3
"""
虚质情报中心 - 动态种子采集器 (周期触发版)
每个硬件周期启动时自动运行，从顶级信息源抓取最新内容。
"""

import feedparser
import os
import re
import json
import random
import sys
from datetime import datetime
from typing import List, Dict, Any

# ==================== 配置区域 ====================
OUTPUT_DIR = "/home/summer/xuzhi_genesis/centers/intelligence/seeds"
CONFIG_DIR = "/home/summer/xuzhi_genesis/centers/intelligence/config"

# 核心源（每个周期必抓）—— 公认的顶级信息源头
CORE_SOURCES = [
    {"url": "https://arxiv.org/rss/cs.AI", "name": "arXiv_AI", "tier": "A"},
    {"url": "https://www.nature.com/nature.rss", "name": "Nature", "tier": "A"},
    {"url": "https://www.quantamagazine.org/feed", "name": "Quanta", "tier": "A"},
    {"url": "https://www.edge.org/feed", "name": "Edge", "tier": "A"},
    {"url": "https://www.science.org/feed/rss", "name": "Science", "tier": "A"},
]

# 卫星源池（从中随机挑选，每个周期轮换）
SATELLITE_SOURCES_POOL = [
    {"url": "https://www.wired.com/feed/rss", "name": "Wired", "tier": "B"},
    {"url": "http://feeds.feedburner.com/TechCrunch", "name": "TechCrunch", "tier": "B"},
    {"url": "https://www.theverge.com/rss/index.xml", "name": "TheVerge", "tier": "B"},
    {"url": "https://feeds.bloomberg.com/markets/news.rss", "name": "Bloomberg", "tier": "B"},
    {"url": "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml", "name": "NYTimes", "tier": "B"},
    {"url": "https://feeds.bbci.co.uk/news/rss.xml", "name": "BBC", "tier": "B"},
    {"url": "https://www.economist.com/feeds/print-sections/77/business.xml", "name": "Economist", "tier": "A"},
    {"url": "https://www.technologyreview.com/feed", "name": "MIT_TechnologyReview", "tier": "A"},
    {"url": "https://academic.oup.com/rss", "name": "OxfordAcademic", "tier": "A"},
    {"url": "https://www.pnas.org/rss", "name": "PNAS", "tier": "A"},
]

# 每个周期从卫星池中随机选取的数量
SATELLITE_COUNT_PER_CYCLE = 5

# 每个源最多取多少条最新条目
MAX_PER_SOURCE = 5

# 摘要最大长度（字符数）
MAX_SUMMARY_LEN = 400

# ==================== 核心函数 ====================

def ensure_directories():
    """确保输出目录存在"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(CONFIG_DIR, exist_ok=True)

def get_cycle_sources():
    """获取本周期要抓取的源列表（核心源 + 随机卫星源）"""
    # 从卫星池随机选取
    selected = random.sample(
        SATELLITE_SOURCES_POOL, 
        min(SATELLITE_COUNT_PER_CYCLE, len(SATELLITE_SOURCES_POOL))
    )
    
    all_sources = CORE_SOURCES + selected
    random.shuffle(all_sources)  # 打乱顺序
    
    # 记录本次源，便于复盘
    source_record = {
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "core_count": len(CORE_SOURCES),
        "satellite_count": len(selected),
        "sources": [s["name"] for s in all_sources]
    }
    record_path = os.path.join(CONFIG_DIR, f"sources_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    with open(record_path, 'w', encoding='utf-8') as f:
        json.dump(source_record, f, indent=2, ensure_ascii=False)
    
    return all_sources

def fetch_feed(url, timeout=10):
    """抓取RSS feed，返回条目列表"""
    try:
        feed = feedparser.parse(url)
        return feed.entries
    except Exception as e:
        print(f"抓取失败 {url}: {e}")
        return []

def clean_text(text):
    """清理文本：移除多余空白、HTML标签等"""
    if not text:
        return ""
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def extract_core_idea(text):
    """提取核心观点（比简单截取更智能）"""
    sentences = re.split(r'[。！？.!?]', text)
    core = '。'.join(sentences[:3]) if sentences else text
    if len(core) > MAX_SUMMARY_LEN:
        core = core[:MAX_SUMMARY_LEN] + "…"
    return core

def generate_summary(entry):
    """生成条目的极简摘要"""
    title = clean_text(entry.get('title', '无标题'))
    
    summary = entry.get('summary', '')
    if not summary and 'content' in entry and entry.content:
        content = entry.content[0].value if entry.content else ''
        summary = clean_text(content)
    else:
        summary = clean_text(summary)
    
    core_idea = extract_core_idea(summary)
    
    return f"**{title}**\n\n{core_idea}\n\n"

def generate_cycle_file():
    """生成周期种子文件"""
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H%M%S")
    filename = f"{date_str}_{time_str}_seeds.md"
    filepath = os.path.join(OUTPUT_DIR, filename)
    
    sources = get_cycle_sources()
    
    lines = []
    lines.append(f"# 心智种子 - {date_str} {time_str}\n")
    lines.append(f"生成时间：{now.strftime('%Y-%m-%d %H:%M:%S')}\n")
    lines.append(f"本次源：{', '.join([s['name'] for s in sources])}\n")
    lines.append("---\n")
    
    total_entries = 0
    all_summaries = []
    
    for source in sources:
        print(f"正在抓取: {source['name']}")
        entries = fetch_feed(source['url'])
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
    
    # 添加本次总览
    lines.append(f"\n## 本次收录总览\n")
    lines.append(f"共收录 {total_entries} 条种子，来自 {len(sources)} 个源\n")
    lines.append("### 来源分布\n")
    for summary in all_summaries:
        lines.append(f"- [{summary['source']}] {summary['title']} ([链接]({summary['link']}))\n")
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.writelines(lines)
    
    print(f"种子文件已生成: {filepath}")
    return filepath

def main():
    ensure_directories()
    generate_cycle_file()

if __name__ == "__main__":
    main()
EOF

chmod +x "$COLLECTOR_SCRIPT"
echo -e "${GREEN}✅ 采集器脚本创建成功${NC}"

# --- 步骤 5: 修改 cycle_engine.sh 实现周期触发 ---
echo -e "\n${YELLOW}🔄 正在集成到周期引擎 (cycle_engine.sh)...${NC}"

if [ ! -f "$CYCLE_ENGINE" ]; then
    echo -e "${RED}❌ cycle_engine.sh 不存在，请手动集成: 在周期开始时执行 $COLLECTOR_SCRIPT${NC}"
else
    # 备份原文件
    cp "$CYCLE_ENGINE" "$CYCLE_ENGINE.bak.$(date +%Y%m%d%H%M%S)"
    echo -e "${GREEN}✅ 已备份 cycle_engine.sh${NC}"
    
    # 定义要插入的代码块
    INSERT_CODE="# Intelligence Center seed collection (triggered on cycle start)\nif [ -x $COLLECTOR_SCRIPT ]; then\n    $COLLECTOR_SCRIPT >> $INTEL_DIR/collector.log 2>&1 &\nfi\n"
    
    # 检查是否已存在调用，避免重复插入
    if grep -q "seed_collector.py" "$CYCLE_ENGINE"; then
        echo -e "${YELLOW}⚠️  检测到已有 seed_collector 调用，跳过修改${NC}"
    else
        # 在 exit 0 或 exit 语句之前插入，如果没有 exit 则在文件末尾追加
        if grep -q "^exit" "$CYCLE_ENGINE"; then
            # 在第一个 exit 前插入
            sed -i "/^exit/i\\$INSERT_CODE" "$CYCLE_ENGINE"
            echo -e "${GREEN}✅ 已在 exit 前插入调用${NC}"
        else
            # 追加到文件末尾
            echo -e "\n$INSERT_CODE" >> "$CYCLE_ENGINE"
            echo -e "${GREEN}✅ 已追加调用到文件末尾${NC}"
        fi
    fi
fi

# --- 步骤 6: 立即运行一次采集验证 ---
echo -e "\n${YELLOW}🔄 立即运行一次采集以验证功能...${NC}"
python3 "$COLLECTOR_SCRIPT"

# 查找最新生成的种子文件
LATEST_SEED=$(ls -t "$SEEDS_DIR"/*.md 2>/dev/null | head -n1)
if [ -f "$LATEST_SEED" ]; then
    echo -e "${GREEN}✅ 最新种子文件: $LATEST_SEED${NC}"
    echo -e "${BLUE}--- 文件预览 (前10行) ---${NC}"
    head -n 10 "$LATEST_SEED"
    echo -e "${BLUE}------------------------${NC}"
else
    echo -e "${YELLOW}⚠️  未生成种子文件，请检查脚本输出${NC}"
fi

# --- 步骤 7: 完成信息 ---
echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}✅ 情报中心部署完成！${NC}"
echo -e "${GREEN}========================================${NC}"
echo -e "📁 采集器脚本: $COLLECTOR_SCRIPT"
echo -e "📁 种子存储目录: $SEEDS_DIR"
echo -e "📁 配置目录: $CONFIG_DIR"
echo -e "📁 备份目录: $BACKUP_DIR"
echo -e ""
echo -e "${BLUE}下次系统周期启动时，采集器将自动运行。您也可手动执行：${NC}"
echo -e "  $COLLECTOR_SCRIPT"
echo -e ""
echo -e "${YELLOW}如需调整采集源或参数，请编辑: $COLLECTOR_SCRIPT${NC}"
echo -e "${YELLOW}查看运行日志: tail -f $INTEL_DIR/collector.log${NC}"

