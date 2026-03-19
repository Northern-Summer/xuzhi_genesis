#!/usr/bin/env python3
"""
元发现调度器：从源之书中探测和更新源的健康状态
"""

import json
import os
import requests
import time
import logging
from datetime import datetime
from typing import Dict, Any

CONFIG_DIR = "/home/summer/xuzhi_genesis/centers/intelligence/config"
ARK_FILE = os.path.join(CONFIG_DIR, "source_ark.json")
QUALITY_FILE = os.path.join(CONFIG_DIR, "source_quality.json")
LOG_FILE = "/home/summer/xuzhi_genesis/centers/intelligence/metascout.log"

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

def probe_source(source):
    """探测单个源的可达性和响应"""
    url = source.get("url", "")
    if not url:
        return {"success": False, "reason": "no_url"}
    
    try:
        # 简单 HEAD 请求，部分源不支持则用 GET
        try:
            resp = requests.head(url, timeout=REQUEST_TIMEOUT, headers={'User-Agent': USER_AGENT})
        except:
            resp = requests.get(url, timeout=REQUEST_TIMEOUT, headers={'User-Agent': USER_AGENT}, stream=True)
            resp.close()
        
        return {
            "success": 200 <= resp.status_code < 400,
            "status_code": resp.status_code,
            "reason": "ok" if 200 <= resp.status_code < 400 else f"http_{resp.status_code}"
        }
    except requests.exceptions.Timeout:
        return {"success": False, "reason": "timeout"}
    except requests.exceptions.ConnectionError:
        return {"success": False, "reason": "connection_error"}
    except Exception as e:
        return {"success": False, "reason": str(e)[:50]}

def main():
    print("🔍 元发现调度器启动")
    ark = load_json(ARK_FILE)
    
    # 加载或初始化质量数据库
    try:
        quality = load_json(QUALITY_FILE)
    except:
        quality = {"sources": []}
    
    # 建立现有源 URL 到记录的映射
    existing = {s.get("url"): s for s in quality.get("sources", [])}
    
    updated = 0
    for src in ark.get("sources", []):
        url = src.get("url")
        if not url:
            continue
        
        print(f"  🔍 探测: {src.get('name')} ({url[:50]}...)")
        probe_result = probe_source(src)
        
        # 更新或创建质量记录
        if url in existing:
            record = existing[url]
        else:
            record = {
                "name": src.get("name"),
                "url": url,
                "type": src.get("type"),
                "category": src.get("category"),
                "authority_level": src.get("authority_level", "C"),
                "attempts": 0,
                "successes": 0,
                "last_check": None,
                "last_status": "unknown",
                "health_score": 0.5
            }
            existing[url] = record
        
        record["attempts"] += 1
        if probe_result["success"]:
            record["successes"] += 1
            record["last_status"] = "success"
            record["health_score"] = min(1.0, record.get("health_score", 0.5) + 0.1)
        else:
            record["last_status"] = "failure"
            record["health_score"] = max(0.1, record.get("health_score", 0.5) - 0.2)
        record["last_check"] = datetime.now().isoformat()
        record["last_probe_detail"] = probe_result
        
        updated += 1
        time.sleep(0.5)  # 礼貌间隔
    
    # 写回质量数据库
    quality["sources"] = list(existing.values())
    save_json(QUALITY_FILE, quality)
    print(f"✅ 元探测完成，更新 {updated} 个源的状态")
    logging.info(f"Metadata scout completed, updated {updated} sources")

if __name__ == "__main__":
    main()
