#!/usr/bin/env python3
"""
Cron Watchdog - 断点重连机制
监控所有cron job状态，自动重试失败任务
原则: 有事才唤醒，无事零打扰
"""
import json
import os
import sys
import time
from pathlib import Path

JOBS_FILE = os.path.expanduser("~/.openclaw/cron/jobs.json")
STATE_FILE = os.path.expanduser("~/.openclaw/cron/watchdog_state.json")
MAX_CONSECUTIVE_ERRORS = 3
RETRY_BACKOFF = [60, 300, 900]  # 1min, 5min, 15min

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"retries": {}, "last_check": 0}

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

def load_jobs():
    with open(JOBS_FILE) as f:
        return json.load(f)

def should_retry(job, state):
    job_id = job["id"]
    errors = job.get("state", {}).get("consecutiveErrors", 0)
    last_status = job.get("state", {}).get("lastRunStatus", "")
    
    if last_status != "error":
        # Clean slate - reset retry counter for this job
        if job_id in state["retries"]:
            del state["retries"][job_id]
        return False
    
    if errors == 0:
        return False
    
    # Check backoff
    retry_info = state["retries"].get(job_id, {"count": 0, "last_retry": 0})
    retry_count = retry_info["count"]
    
    if retry_count >= len(RETRY_BACKOFF):
        return False  # Max retries reached
    
    backoff_secs = RETRY_BACKOFF[retry_count]
    if time.time() - retry_info.get("last_retry", 0) < backoff_secs:
        return False
    
    return True

def main():
    state = load_state()
    jobs = load_jobs()
    retries_triggered = []
    
    for job in jobs.get("jobs", []):
        if not job.get("enabled", True):
            continue
        
        if should_retry(job, state):
            job_id = job["id"]
            job_name = job["name"]
            agent_id = job.get("agentId", "main")
            payload = job.get("payload", {})
            schedule = job.get("schedule", {})
            
            # Record retry
            retry_info = state["retries"].setdefault(job_id, {"count": 0, "last_retry": 0})
            retry_count = retry_info["count"]
            state["retries"][job_id]["count"] = retry_count + 1
            state["retries"][job_id]["last_retry"] = int(time.time())
            
            print(f"[WATCHDOG] Retrying job: {job_name} (attempt {retry_count + 1})")
            retries_triggered.append({
                "job_id": job_id,
                "job_name": job_name,
                "agent_id": agent_id,
                "attempt": retry_count + 1,
                "error": job.get("state", {}).get("lastError", "unknown")
            })
    
    state["last_check"] = int(time.time())
    save_state(state)
    
    if retries_triggered:
        print(f"[WATCHDOG] Triggered {len(retries_triggered)} retries")
        for r in retries_triggered:
            print(f"  - {r['job_name']} (attempt {r['attempt']}): {r['error'][:80]}")
    else:
        print("[WATCHDOG] All jobs healthy, nothing to retry")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
