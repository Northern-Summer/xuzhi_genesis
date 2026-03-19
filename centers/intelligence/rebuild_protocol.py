#!/usr/bin/env python3
"""
重建协议：当所有实时源失效时，从源之书重新激活系统
"""

import json
import os
import sys
from datetime import datetime

CONFIG_DIR = "/home/summer/xuzhi_genesis/centers/intelligence/config"
ARK_FILE = os.path.join(CONFIG_DIR, "source_ark.json")
QUALITY_FILE = os.path.join(CONFIG_DIR, "source_quality.json")
CANDIDATE_FILE = os.path.join(CONFIG_DIR, "candidate_sources.json")
REBUILD_LOG = "/home/summer/xuzhi_genesis/centers/intelligence/rebuild.log"

def log(msg):
    with open(REBUILD_LOG, 'a') as f:
        f.write(f"{datetime.now().isoformat()} - {msg}\n")
    print(f"🔄 {msg}")

def main():
    log("🚨 重建协议触发：检测到所有实时源失效")
    
    # 加载源之书
    with open(ARK_FILE, 'r') as f:
        ark = json.load(f)
    
    # 清空候选池，准备重建
    candidates = {"candidates": []}
    
    # 从源之书选取权威等级 A 的源作为初始重建种子
    a_sources = [s for s in ark.get("sources", []) if s.get("authority_level") == "A"]
    log(f"从源之书选取 {len(a_sources)} 个 A 级源作为重建种子")
    
    for src in a_sources[:20]:  # 先重建前20个最权威的
        candidate = {
            "url": src["url"],
            "name": src.get("name", ""),
            "type": src.get("type", "unknown"),
            "category": src.get("category", ""),
            "authority_level": src.get("authority_level", "C"),
            "source_url": "source_ark",
            "discovered_at": datetime.now().isoformat(),
            "discovered_from": "rebuild_protocol",
            "attempts": 0,
            "successes": 0,
            "last_check": None,
            "status": "candidate",
            "note": "重建协议注入"
        }
        candidates["candidates"].append(candidate)
    
    # 写入候选池
    with open(CANDIDATE_FILE, 'w') as f:
        json.dump(candidates, f, indent=2)
    
    log(f"✅ 重建协议完成，候选池已注入 {len(candidates['candidates'])} 个源")
    log("系统将逐步重新探测这些源，恢复实时采集能力")

if __name__ == "__main__":
    main()
