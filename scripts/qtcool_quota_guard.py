#!/usr/bin/env python3
"""Qtcool配额守护：检查当日gateway.log中qtcool/gpt-5费用，超阈值则切回infini"""
import json, os, re, glob, sys

LOG_GLOB = os.path.expanduser("~/.openclaw/logs/gateway.log")
CAP_USD = 1.0
THRESHOLD = 0.85
TODAY = __import__("datetime").date.today().isoformat()

# Scan gateway log(s)
total = 0.0
for log_path in glob.glob(LOG_GLOB):
    try:
        with open(log_path) as f:
            for line in f:
                if TODAY not in line:
                    continue
                if "qtcool" not in line.lower() and "gpt-5" not in line:
                    continue
                # Match "$X.XX" patterns
                for m in re.finditer(r'\$([0-9]+\.[0-9]+)', line):
                    total += float(m.group(1))
    except Exception:
        pass

print(f"qtcool-gpt5 today: ${total:.4f} / ${CAP_USD:.2f}")
if total >= CAP_USD * THRESHOLD:
    cfg_path = os.path.expanduser("~/.openclaw/openclaw.json")
    cfg = json.load(open(cfg_path))
    new = "custom-cloud-infini-ai-com/minimax-m2.7"
    if cfg["agents"]["defaults"]["model"]["primary"] != new:
        cfg["agents"]["defaults"]["model"]["primary"] = new
        json.dump(cfg, open(cfg_path, "w"), indent=2)
        print("SWITCHED to infini/minimax-m2.7")
    else:
        print("already-on-infini")
else:
    print("OK - quota-safe")
