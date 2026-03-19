#!/bin/bash
#
# enhance_contribution_score.sh - 增强贡献分计算，引入引用源权重
#

set -e

PROJECT_ROOT="/home/summer/xuzhi_genesis"
INTEL_DIR="$PROJECT_ROOT/centers/intelligence"
CONFIG_DIR="$INTEL_DIR/config"
QUALITY_FILE="$CONFIG_DIR/source_quality.json"
MIND_DIR="$PROJECT_ROOT/centers/mind"
RATINGS_FILE="$MIND_DIR/society/ratings.json"
BACKUP_DIR="$PROJECT_ROOT/backups/contribution_enhance_$(date +%Y%m%d%H%M%S)"

echo -e "\033[0;34m========================================\033[0m"
echo -e "\033[0;34m  增强贡献分计算：引入引用源权重\033[0m"
echo -e "\033[0;34m========================================\033[0m\n"

# 备份
mkdir -p "$BACKUP_DIR"
cp "$QUALITY_FILE" "$BACKUP_DIR/" 2>/dev/null || true
cp "$INTEL_DIR/track_seed_usage.py" "$BACKUP_DIR/" 2>/dev/null || true
echo -e "\033[0;32m✅ 已备份至: $BACKUP_DIR\033[0m"

# 在 source_quality.json 的 config 中添加引用权重参数
echo -e "\n\033[0;33m▶ 更新 source_quality.json 配置...\033[0m"
python3 << 'EOF'
import json

QUALITY_FILE = "/home/summer/xuzhi_genesis/centers/intelligence/config/source_quality.json"

with open(QUALITY_FILE, 'r') as f:
    data = json.load(f)

if "config" not in data:
    data["config"] = {}

changed = False
# 添加引用权重因子（默认1.0，表示权重=引用者评分/5，即评分5的智能体权重1.0）
if "citation_weight_factor" not in data["config"]:
    data["config"]["citation_weight_factor"] = 1.0
    changed = True
    print("✅ 添加 citation_weight_factor = 1.0")

if changed:
    with open(QUALITY_FILE, 'w') as f:
        json.dump(data, f, indent=2)
else:
    print("ℹ️ 无需修改")
EOF

# 重写 track_seed_usage.py，加入引用源权重
echo -e "\n\033[0;33m▶ 重写 track_seed_usage.py...\033[0m"

cat > "$INTEL_DIR/track_seed_usage.py" << 'EOF'
#!/usr/bin/env python3
"""
种子引用统计（增强版）：解析智能体任务报告，统计每个种子文件被引用的次数，
并根据引用智能体的社会评分进行加权，更新源的贡献分。
"""

import os
import re
import json
from datetime import datetime, timedelta
from typing import Dict, List, Set
import glob

# 配置
PROJECT_ROOT = "/home/summer/xuzhi_genesis"
INTEL_DIR = os.path.join(PROJECT_ROOT, "centers/intelligence")
SEEDS_DIR = os.path.join(INTEL_DIR, "seeds")
TASK_DIR = os.path.join(PROJECT_ROOT, "centers/task")
REPORTS_DIR = os.path.join(TASK_DIR, "reports")  # 任务报告存放目录
QUALITY_FILE = os.path.join(INTEL_DIR, "config/source_quality.json")
RATINGS_FILE = os.path.join(PROJECT_ROOT, "centers/mind/society/ratings.json")

# 贡献分权重（相对于健康分），从 quality.json 读取
CONTRIBUTION_WEIGHT = 0.3  # 默认，会被配置文件覆盖
CITATION_WEIGHT_FACTOR = 1.0  # 默认，会被配置文件覆盖

# 只统计最近30天的种子
MAX_DAYS = 30

def load_json(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"⚠️ 文件不存在: {filepath}")
        return {}
    except json.JSONDecodeError:
        print(f"⚠️ JSON解析错误: {filepath}")
        return {}

def save_json(filepath, data):
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def get_seed_files():
    """获取所有种子文件及其元数据"""
    seeds = []
    cutoff = datetime.now() - timedelta(days=MAX_DAYS)
    for fpath in glob.glob(os.path.join(SEEDS_DIR, "*.md")):
        fname = os.path.basename(fpath)
        # 文件名格式：YYYY-MM-DD_HHMMSS_seeds.md
        match = re.match(r'(\d{4}-\d{2}-\d{2})_\d+_seeds\.md', fname)
        if match:
            date_str = match.group(1)
            seed_date = datetime.strptime(date_str, "%Y-%m-%d")
            if seed_date >= cutoff:
                seeds.append({
                    "file": fpath,
                    "name": fname,
                    "date": seed_date
                })
    return seeds

def get_reports():
    """获取所有任务报告文件"""
    reports = []
    for fpath in glob.glob(os.path.join(REPORTS_DIR, "*.md")):
        reports.append(fpath)
    for fpath in glob.glob(os.path.join(REPORTS_DIR, "*.txt")):
        reports.append(fpath)
    return reports

def get_agent_ratings():
    """读取智能体社会评分"""
    ratings_data = load_json(RATINGS_FILE)
    # 期望格式：{"agent_id": {"score": 6, ...}, ...}
    ratings = {}
    for agent_id, info in ratings_data.items():
        if isinstance(info, dict) and "score" in info:
            ratings[agent_id] = info["score"]
        else:
            # 兼容简单格式
            ratings[agent_id] = info if isinstance(info, (int, float)) else 5
    return ratings

def extract_sources_from_seed(seed_file):
    """从种子文件头部提取源列表"""
    try:
        with open(seed_file, 'r', encoding='utf-8') as f:
            first_line = f.readline().strip()
        if first_line.startswith("<!-- sources:"):
            # 提取 JSON
            json_str = first_line[14:-3]  # 去掉 <!-- sources: 和 -->
            sources = json.loads(json_str)
            return sources
    except Exception as e:
        print(f"  无法解析种子文件头部: {e}")
    return []

def count_references(seed_files, report_files, agent_ratings, weight_factor):
    """统计每个种子文件在报告中被引用的次数，并加权"""
    # 构建种子名到源列表的映射
    seed_to_sources = {}
    for s in seed_files:
        sources = extract_sources_from_seed(s["file"])
        if sources:
            seed_to_sources[s["name"]] = sources
    
    # 初始化加权引用计数
    weighted_counts = {s["name"]: 0.0 for s in seed_files}
    
    for report in report_files:
        # 尝试从报告文件名或内容中提取智能体ID
        agent_id = None
        base = os.path.basename(report)
        # 假设报告文件名格式如 "agent_main_20260318.md"
        match = re.match(r'agent_([a-zA-Z0-9_]+)_', base)
        if match:
            agent_id = match.group(1)
        # 若无法提取，则从内容中查找
        if not agent_id:
            try:
                with open(report, 'r', encoding='utf-8') as f:
                    content_sample = f.read(500)  # 只读前500字符
                match = re.search(r'agent[_-]?([a-zA-Z0-9_]+)', content_sample, re.IGNORECASE)
                if match:
                    agent_id = match.group(1)
            except:
                pass
        
        # 获取智能体评分，若无则默认5
        agent_score = agent_ratings.get(agent_id, 5.0)
        # 计算权重：评分越高权重越大，factor控制缩放
        weight = 1.0 + weight_factor * (agent_score - 5.0) / 5.0  # 基准为1，评分5时权重1
        if weight < 0.1:
            weight = 0.1
        
        try:
            with open(report, 'r', encoding='utf-8') as f:
                content = f.read()
            for seed_name in seed_to_sources.keys():
                if seed_name in content:
                    weighted_counts[seed_name] += weight
        except Exception as e:
            print(f"  无法读取报告 {report}: {e}")
    
    return weighted_counts, seed_to_sources

def update_contribution_scores(weighted_counts, seed_to_sources):
    """根据加权引用计数更新源的贡献分"""
    quality = load_json(QUALITY_FILE)
    sources = quality.get("sources", [])
    config = quality.get("config", {})
    
    # 更新配置中的贡献权重（用于日志）
    global CONTRIBUTION_WEIGHT, CITATION_WEIGHT_FACTOR
    CONTRIBUTION_WEIGHT = config.get("contribution_weight", 0.3)
    CITATION_WEIGHT_FACTOR = config.get("citation_weight_factor", 1.0)
    
    # 建立源名到记录对象的映射（方便更新）
    source_dict = {s.get("name"): s for s in sources if s.get("name")}
    
    # 遍历每个种子，将加权引用计数加到对应源的贡献分上
    for seed_name, weighted_count in weighted_counts.items():
        if weighted_count == 0:
            continue
        src_names = seed_to_sources.get(seed_name, [])
        for src_name in src_names:
            # 模糊匹配：如果源名包含在种子记录的源名中
            # 精确匹配或部分匹配
            matched = None
            for name in source_dict:
                if name == src_name or name in src_name or src_name in name:
                    matched = name
                    break
            if matched:
                src = source_dict[matched]
                old = src.get("contribution_score", 0.0)
                # 增量更新：每次引用加0.1 * 权重，但这里weighted_count已经加权
                src["contribution_score"] = old + 0.1 * weighted_count
                print(f"  ✅ 为源 '{matched}' 增加贡献分 {0.1 * weighted_count:.3f} (原 {old:.3f})")
    
    # 保存
    save_json(QUALITY_FILE, quality)
    print(f"✅ 贡献分更新完成")

def main():
    print("🔍 开始统计种子引用（加权版）...")
    
    # 读取配置
    quality = load_json(QUALITY_FILE)
    config = quality.get("config", {})
    weight_factor = config.get("citation_weight_factor", 1.0)
    
    seeds = get_seed_files()
    reports = get_reports()
    agent_ratings = get_agent_ratings()
    print(f"  找到 {len(seeds)} 个种子文件，{len(reports)} 个任务报告，{len(agent_ratings)} 个智能体评分")
    
    weighted_counts, seed_to_sources = count_references(seeds, reports, agent_ratings, weight_factor)
    total_weighted = sum(weighted_counts.values())
    print(f"  总加权引用次数: {total_weighted:.2f}")
    
    if total_weighted > 0:
        update_contribution_scores(weighted_counts, seed_to_sources)
    else:
        print("  没有新引用，无需更新")
    print("✅ 统计完成")

if __name__ == "__main__":
    main()
EOF

chmod +x "$INTEL_DIR/track_seed_usage.py"
echo -e "\033[0;32m✅ track_seed_usage.py 已增强\033[0m"

# 测试运行
echo -e "\n\033[0;33m▶ 运行测试统计...\033[0m"
python3 "$INTEL_DIR/track_seed_usage.py"

echo -e "\n\033[0;32m========================================\033[0m"
echo -e "\033[0;32m✅ 增强完成！\033[0m"
echo -e "\033[0;32m========================================\033[0m"
echo -e "现在贡献分计算已引入引用源权重："
echo -e "  - 引用自高评分智能体的种子获得更高贡献分"
echo -e "  - 权重因子可调节 (citation_weight_factor)"
echo -e "您可以在 source_quality.json 的 config 中调整该参数。"
