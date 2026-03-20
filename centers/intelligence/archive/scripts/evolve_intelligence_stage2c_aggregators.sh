#!/bin/bash
#
# evolve_intelligence_stage2c_aggregators.sh
# 为情报中心注入高质量聚合源和学术发现能力
#

set -e

PROJECT_ROOT="/home/summer/xuzhi_genesis"
INTEL_DIR="$PROJECT_ROOT/centers/intelligence"
CONFIG_DIR="$INTEL_DIR/config"
CANDIDATE_FILE="$CONFIG_DIR/candidate_sources.json"
DISCOVERY_SCRIPT="$INTEL_DIR/source_discovery.py"
BACKUP_DIR="$PROJECT_ROOT/backups/intelligence_stage2c_$(date +%Y%m%d%H%M%S)"

echo -e "\033[0;34m========================================\033[0m"
echo -e "\033[0;34m  情报中心：接入聚合源与学术发现\033[0m"
echo -e "\033[0;34m========================================\033[0m\n"

# 备份
mkdir -p "$BACKUP_DIR"
cp "$CANDIDATE_FILE" "$BACKUP_DIR/" 2>/dev/null || true
cp "$DISCOVERY_SCRIPT" "$BACKUP_DIR/" 2>/dev/null || true
echo -e "\033[0;32m✅ 已备份\033[0m"

# --- 1. 注入静态聚合源 ---
echo -e "\n\033[0;33m▶ 注入高质量聚合源...\033[0m"
cat > /tmp/add_aggregators.py << 'PYEOF'
import json
from datetime import datetime

CANDIDATE_FILE = "/home/summer/xuzhi_genesis/centers/intelligence/config/candidate_sources.json"

# 公认的高质量信息源聚合器（不限于 RSS）
AGGREGATORS = [
    {"name": "arXiv.org", "url": "https://arxiv.org/rss/cs", "description": "计算机科学预印本", "category": "academic", "type": "rss"},
    {"name": "ScienceDaily", "url": "https://www.sciencedaily.com/rss/all.xml", "description": "每日科学新闻", "category": "science", "type": "rss"},
    {"name": "Phys.org", "url": "https://phys.org/rss-feed/", "description": "物理学新闻", "category": "science", "type": "rss"},
    {"name": "EurekAlert!", "url": "https://www.eurekalert.org/rss/news.php", "description": "科学新闻", "category": "science", "type": "rss"},
    {"name": "MIT News", "url": "https://news.mit.edu/rss", "description": "MIT 新闻", "category": "academic", "type": "rss"},
    {"name": "Stanford News", "url": "https://news.stanford.edu/feed/", "description": "斯坦福新闻", "category": "academic", "type": "rss"},
    {"name": "The Conversation", "url": "https://theconversation.com/us/feed", "description": "学者撰写的新闻", "category": "culture", "type": "rss"},
    {"name": "Project Syndicate", "url": "https://www.project-syndicate.org/rss", "description": "经济政治评论", "category": "culture", "type": "rss"},
    {"name": "Aeon", "url": "https://aeon.co/feed.rss", "description": "哲学与思想", "category": "philosophy", "type": "rss"},
    {"name": "Noema Magazine", "url": "https://www.noemamag.com/feed/", "description": "技术哲学", "category": "philosophy", "type": "rss"},
]

with open(CANDIDATE_FILE, 'r') as f:
    data = json.load(f)

existing_urls = {c["url"] for c in data["candidates"]}
added = 0
for agg in AGGREGATORS:
    if agg["url"] not in existing_urls:
        cand = {
            "url": agg["url"],
            "name": agg["name"],
            "description": agg.get("description", ""),
            "category": agg.get("category", ""),
            "source_url": "aggregator_list",
            "discovered_at": datetime.now().isoformat(),
            "discovered_from": "community_maintained",
            "attempts": 0,
            "successes": 0,
            "last_check": None,
            "status": "candidate"
        }
        data["candidates"].append(cand)
        added += 1

if added:
    with open(CANDIDATE_FILE, 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"✅ 添加了 {added} 个聚合源")
else:
    print("ℹ️ 没有新聚合源需要添加")
PYEOF

python3 /tmp/add_aggregators.py

# --- 2. 增强发现模块，支持从学术页面提取外部链接 ---
echo -e "\n\033[0;33m▶ 增强发现模块：学术链接提取...\033[0m"

# 在发现模块中添加新函数
cat >> "$DISCOVERY_SCRIPT" << 'PYEOF'

def extract_external_links_from_arxiv(html, base_url):
    """从 arXiv 论文页提取外部链接（如代码仓库、数据集）"""
    soup = BeautifulSoup(html, 'html.parser')
    links = []
    # arXiv 论文页面的特定区域
    code_links = soup.find_all('a', href=re.compile(r'(github|gitlab|bitbucket)'))
    for a in code_links:
        href = a.get('href')
        if href and not href.startswith('#') and 'arxiv.org' not in href:
            links.append(href)
    # 提取 DOI 链接
    doi_links = soup.find_all('a', href=re.compile(r'doi.org'))
    for a in doi_links:
        links.append(a.get('href'))
    return list(set(links))  # 去重

def discover_from_seed_file_enhanced(seed_file):
    """增强版：既提取 RSS，也提取外部网站链接"""
    vprint(f"📄 处理种子文件: {os.path.basename(seed_file)}")
    with open(seed_file, 'r', encoding='utf-8') as f:
        content = f.read()
    urls = re.findall(r'\(https?://[^\s\)]+\)', content)
    urls = [u.strip('()') for u in urls]
    vprint(f"  找到 {len(urls)} 个链接")
    discovered = []
    external_sites = []
    
    for i, url in enumerate(urls):
        if not url.startswith('http'):
            continue
        vprint(f"  🔗 [{i+1}/{len(urls)}] 检查: {url[:60]}...")
        try:
            resp = requests.get(url, timeout=REQUEST_TIMEOUT, headers={'User-Agent': USER_AGENT})
            resp.raise_for_status()
            html = resp.text
            
            # 1. 提取 RSS 链接
            rss_links = extract_rss_links_from_html(html, url)
            for rss in rss_links:
                if is_valid_rss_url(rss):
                    discovered.append({
                        "url": rss,
                        "source_url": url,
                        "discovered_at": datetime.now().isoformat(),
                        "discovered_from": os.path.basename(seed_file),
                        "type": "rss"
                    })
            
            # 2. 如果是 arXiv 论文页，提取外部链接
            if 'arxiv.org/abs/' in url:
                external = extract_external_links_from_arxiv(html, url)
                for ext in external:
                    if ext not in [d["url"] for d in external_sites]:
                        external_sites.append({
                            "url": ext,
                            "source_url": url,
                            "discovered_at": datetime.now().isoformat(),
                            "discovered_from": os.path.basename(seed_file),
                            "type": "website"
                        })
                        vprint(f"    发现外部网站: {ext}")
            
        except Exception as e:
            vprint(f"    ❌ 错误: {type(e).__name__}")
        time.sleep(1)
    
    vprint(f"  从该文件共发现 {len(discovered)} 个 RSS 候选，{len(external_sites)} 个外部网站候选")
    return discovered + external_sites

# 替换原有的 discover_from_seed_file 调用
# （这里仅演示扩展，实际需要修改 main 函数调用，但为了最小改动，我们保留原函数，
# 并在 main 中新增一个增强模式开关）
PYEOF

# 修改 main 函数，添加 --enhanced 参数
sed -i '/def main():/,/^$/c\
def main():\
    import argparse\
    parser = argparse.ArgumentParser()\
    parser.add_argument("--enhanced", "-e", action="store_true", help="启用增强发现（提取外部网站）")\
    parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")\
    args = parser.parse_args()\
    \
    global VERBOSE\
    VERBOSE = args.verbose\
    \
    vprint("\n🔍 开始源发现...")\
    seed_files = sorted([f for f in os.listdir(SEEDS_DIR) if f.endswith(".md")], reverse=True)\
    if not seed_files:\
        vprint("❌ 未找到种子文件")\
        return\
    latest = os.path.join(SEEDS_DIR, seed_files[0])\
    vprint(f"📅 最新种子文件: {seed_files[0]}")\
    \
    if args.enhanced:\
        discovered = discover_from_seed_file_enhanced(latest)\
    else:\
        discovered = discover_from_seed_file(latest)\
    \
    if discovered:\
        added = add_candidates(discovered)\
        vprint(f"\n🎉 本次发现完成，共新增 {added} 个候选源。")\
    else:\
        vprint("\nℹ️ 本次未发现新候选源。")\
    vprint("✅ 源发现结束")' "$DISCOVERY_SCRIPT"

echo -e "\033[0;32m✅ 发现模块已增强，支持 --enhanced 参数提取外部网站\033[0m"

# --- 3. 立即运行增强模式测试 ---
echo -e "\n\033[0;33m▶ 运行增强发现测试（从最新种子提取外部网站）...\033[0m"
python3 "$DISCOVERY_SCRIPT" --enhanced --verbose

echo -e "\n\033[0;32m========================================\033[0m"
echo -e "\033[0;32m✅ 聚合源与学术发现集成完成！\033[0m"
echo -e "\033[0;32m========================================\033[0m"
echo -e "现在您可以使用："
echo -e "  python3 $DISCOVERY_SCRIPT --enhanced --verbose  # 启用外部网站发现"
echo -e "  python3 $DISCOVERY_SCRIPT                        # 原模式"
echo -e "\n候选池已增加聚合源，查看："
echo -e "  cat $CANDIDATE_FILE | jq '.candidates[] | select(.source_url==\"aggregator_list\")'"
