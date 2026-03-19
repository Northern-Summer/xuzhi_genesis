#!/usr/bin/env python3
"""
虚质情报中心 - 源发现引擎（增强版）
支持从种子页面提取RSS和外部网站链接，并提供详细输出。
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
import sys
import argparse
from typing import List, Dict, Any

# 配置
CONFIG_DIR = "/home/summer/xuzhi_genesis/centers/intelligence/config"
SEEDS_DIR = "/home/summer/xuzhi_genesis/centers/intelligence/seeds"
CANDIDATE_FILE = os.path.join(CONFIG_DIR, "candidate_sources.json")
QUALITY_FILE = os.path.join(CONFIG_DIR, "source_quality.json")
LOG_FILE = "/home/summer/xuzhi_genesis/centers/intelligence/discovery.log"

# 全局 verbose 标志
VERBOSE = False

# 设置日志
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def vprint(*args, **kwargs):
    """详细输出（仅在 verbose 模式）"""
    if VERBOSE:
        print(*args, **kwargs, flush=True)

REQUEST_TIMEOUT = 10
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

def load_json(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        vprint(f"⚠️ 文件不存在: {filepath}")
        return {"candidates": []} if "candidate" in filepath else {"sources": []}
    except json.JSONDecodeError:
        vprint(f"⚠️ JSON 解析错误: {filepath}")
        return {"candidates": []} if "candidate" in filepath else {"sources": []}

def save_json(filepath, data):
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def is_valid_rss_url(url):
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return False
    path = parsed.path.lower()
    if any(ext in path for ext in ['.rss', '.xml', 'feed', 'atom', 'rss']):
        return True
    return False

def extract_rss_links_from_html(html, base_url):
    soup = BeautifulSoup(html, 'html.parser')
    links = []
    for link in soup.find_all('link', type=re.compile(r'application/(rss|atom)\+xml')):
        href = link.get('href')
        if href:
            absolute = urljoin(base_url, href)
            links.append(absolute)
    return links

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

def discover_from_seed_file(seed_file):
    """基础发现：仅提取 RSS 链接"""
    vprint(f"📄 处理种子文件: {os.path.basename(seed_file)}")
    with open(seed_file, 'r', encoding='utf-8') as f:
        content = f.read()
    urls = re.findall(r'\(https?://[^\s\)]+\)', content)
    urls = [u.strip('()') for u in urls]
    vprint(f"  找到 {len(urls)} 个链接")
    discovered = []
    
    for i, url in enumerate(urls):
        if not url.startswith('http'):
            continue
        vprint(f"  🔗 [{i+1}/{len(urls)}] 检查: {url[:60]}...")
        try:
            resp = requests.get(url, timeout=REQUEST_TIMEOUT, headers={'User-Agent': USER_AGENT})
            resp.raise_for_status()
            html = resp.text
            rss_links = extract_rss_links_from_html(html, url)
            if rss_links:
                vprint(f"    发现 {len(rss_links)} 个 RSS 链接")
            for rss in rss_links:
                if is_valid_rss_url(rss):
                    discovered.append({
                        "url": rss,
                        "source_url": url,
                        "discovered_at": datetime.now().isoformat(),
                        "discovered_from": os.path.basename(seed_file),
                        "type": "rss"
                    })
        except requests.exceptions.Timeout:
            vprint(f"    ⏱️ 超时")
        except requests.exceptions.ConnectionError:
            vprint(f"    🔌 连接错误")
        except Exception as e:
            vprint(f"    ❌ 错误: {type(e).__name__}")
        time.sleep(1)
    vprint(f"  从该文件共发现 {len(discovered)} 个候选源")
    return discovered

def discover_from_seed_file_enhanced(seed_file):
    """增强发现：既提取 RSS，也提取外部网站链接（如 arXiv 代码库）"""
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
            
        except requests.exceptions.Timeout:
            vprint(f"    ⏱️ 超时")
        except requests.exceptions.ConnectionError:
            vprint(f"    🔌 连接错误")
        except Exception as e:
            vprint(f"    ❌ 错误: {type(e).__name__}")
        time.sleep(1)
    
    vprint(f"  从该文件共发现 {len(discovered)} 个 RSS 候选，{len(external_sites)} 个外部网站候选")
    return discovered + external_sites

def add_candidates(new_candidates):
    data = load_json(CANDIDATE_FILE)
    existing_urls = {c["url"] for c in data["candidates"]}
    quality = load_json(QUALITY_FILE)
    main_urls = {s["url"] for s in quality.get("sources", [])}
    added = 0
    for cand in new_candidates:
        if cand["url"] not in existing_urls and cand["url"] not in main_urls:
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
        vprint(f"✅ 新增 {added} 个候选源")
    else:
        vprint("ℹ️ 没有新候选源需要添加")
    return added

def main():
    global VERBOSE
    parser = argparse.ArgumentParser(description="源发现引擎")
    parser.add_argument("--enhanced", "-e", action="store_true", help="启用增强发现（提取外部网站）")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")
    args = parser.parse_args()
    
    VERBOSE = args.verbose
    
    vprint("\n🔍 开始源发现...")
    seed_files = sorted([f for f in os.listdir(SEEDS_DIR) if f.endswith(".md")], reverse=True)
    if not seed_files:
        vprint("❌ 未找到种子文件")
        logging.warning("No seed files found.")
        return
    latest = os.path.join(SEEDS_DIR, seed_files[0])
    vprint(f"📅 最新种子文件: {seed_files[0]}")
    
    if args.enhanced:
        discovered = discover_from_seed_file_enhanced(latest)
    else:
        discovered = discover_from_seed_file(latest)
    
    if discovered:
        added = add_candidates(discovered)
        vprint(f"\n🎉 本次发现完成，共新增 {added} 个候选源。")
    else:
        vprint("\nℹ️ 本次未发现新候选源。")
    vprint("✅ 源发现结束")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        vprint("\n⚠️ 用户中断")
        sys.exit(130)
    except Exception as e:
        vprint(f"\n❌ 未预期错误: {type(e).__name__}: {e}")
        logging.exception("Unhandled exception")
        sys.exit(1)
