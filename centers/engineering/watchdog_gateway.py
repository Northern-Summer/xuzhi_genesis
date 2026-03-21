#!/usr/bin/env python3
"""
Gateway Watchdog — Xuzhi Phase 4 Core
Λ (Lambda-Ergo) | Engineering Center

只通过 HTTP 判断 gateway 是否健康，不用 openclaw status 命令。
正确识别：进程存在但 HTTP 无响应 = 需要重启。
"""
import os, time, sys, urllib.request, urllib.error

GATEWAY_URL = "http://localhost:18789/"
HEALTH_URL = "http://localhost:18789/health"
CHECKPOINT_FILE = os.path.expanduser("~/.openclaw/workspace/memory/checkpoint.json")
LAST_RESTART_FILE = os.path.expanduser("~/.openclaw/workspace/memory/last_gateway_restart.txt")
RESTART_COOLDOWN = 900  # 15 minutes between restarts

def http_check(url, timeout=5):
    """Returns (healthy, detail)"""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "XuzhiWatchdog/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read(200)
            return True, f"HTTP {r.status}, {len(body)} bytes"
    except urllib.error.HTTPError as e:
        return True, f"HTTP {e.code} (gateway alive)"
    except Exception as e:
        return False, str(e)

def read_last_restart():
    if os.path.exists(LAST_RESTART_FILE):
        try:
            return float(open(LAST_RESTART_FILE).read().strip())
        except:
            pass
    return 0

def write_last_restart():
    with open(LAST_RESTART_FILE, "w") as f:
        f.write(str(time.time()))

def restart_via_systemd():
    """Restart gateway via systemd (rate-limited)"""
    last = read_last_restart()
    if time.time() - last < RESTART_COOLDOWN:
        elapsed = int(time.time() - last)
        print(f"    ⏳ restart cooldown: {elapsed}s elapsed, waiting {RESTART_COOLDOWN - elapsed}s more")
        return False
    print("    🔄 restarting via systemctl...")
    os.system("systemctl restart openclaw 2>/dev/null")
    write_last_restart()
    return True

def is_gateway_process_alive():
    """Check if gateway process exists (not whether it's healthy)"""
    import subprocess
    try:
        r = subprocess.run(["systemctl", "is-active", "openclaw"], capture_output=True, text=True, timeout=3)
        return r.stdout.strip() == "active"
    except:
        return None  # unknown

if __name__ == "__main__":
    print("[Λ] gateway watchdog...")

    # Step 1: HTTP health check
    healthy, detail = http_check(HEALTH_URL)
    if healthy:
        print(f"    ✓ gateway HTTP healthy: {detail}")
        sys.exit(0)

    print(f"    ✗ gateway HTTP unreachable: {detail}")

    # Step 2: Check if process is active
    proc_state = is_gateway_process_alive()
    if proc_state is True:
        print(f"    ⚠ process active but HTTP failing — restart needed")
        restart_via_systemd()
    elif proc_state is False:
        print(f"    ⚠ process not active — restart needed")
        restart_via_systemd()
    else:
        print(f"    ? cannot determine process state — skip restart (avoids false positive)")
