#!/usr/bin/env python3
"""
击鼓传花 — 流动笔记议会引擎 v2
去中心化，无中央协调者，零 LLM 调用。

令牌环模型：
- TOKEN 文件：记载当前令牌持有者
- BELL 文件：铃铛触发标记（有铃响则推进令牌）
- 令牌持有者负责：处理 + 推进令牌到下一个

失效检测：
1. 令牌持有者 N 分钟无动静 → 超时转移令牌
2. 铃响 N 次但令牌持有者不变 → 跳过持有者
3. 文件锁防竞态
4. proposals.json + flow.json 双写一致性保证
"""
import json
import sys
import os
import fcntl
import argparse
import time
from pathlib import Path
from datetime import datetime, timezone, timedelta

PARLIAMENT_DIR = Path(__file__).parent
FLOW_FILE = PARLIAMENT_DIR / "flow.json"
TOKEN_FILE = PARLIAMENT_DIR / ".token"
BELL_FILE = PARLIAMENT_DIR / ".bell"
LOCK_FILE = PARLIAMENT_DIR / ".ring.lock"
PROPOSALS_FILE = PARLIAMENT_DIR / "proposals.json"

RING = ["Φ", "Δ", "Θ", "Γ", "Ω", "Ψ", "Ξ"]
TOKEN_TIMEOUT_SECONDS = 600       # 令牌持有者 10 分钟无动作则超时转移
BELL_STUCK_THRESHOLD = 3          # 铃响 N 次持有者不变则跳过
BELL_COOLDOWN = 60                # 铃铛冷却秒数（防止高频触发）

# ─────────────────────────────────────────────────────────
# 工具
# ─────────────────────────────────────────────────────────

def load_json(path):
    with open(path) as f:
        return json.load(f)


def save_json(path, data):
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)


def acquire_lock():
    """文件锁防竞态"""
    lock_fd = open(LOCK_FILE, 'w')
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return lock_fd
    except BlockingIOError:
        lock_fd.close()
        return None


def load_flow():
    with open(FLOW_FILE) as f:
        return json.load(f)


def save_flow(flow):
    with open(FLOW_FILE, 'w') as f:
        json.dump(flow, f, indent=2)


def load_token():
    """读取令牌状态"""
    if not TOKEN_FILE.exists():
        return None, None
    try:
        with open(TOKEN_FILE) as f:
            d = json.load(f)
        return d.get("holder"), d.get("since")
    except:
        return None, None


def save_token(holder):
    """写入令牌"""
    with open(TOKEN_FILE, 'w') as f:
        json.dump({
            "holder": holder,
            "since": datetime.now(timezone.utc).isoformat(),
            "bell_count": 0
        }, f)


def advance_token(current):
    """令牌传递给下一个"""
    idx = RING.index(current) if current in RING else -1
    return RING[(idx + 1) % len(RING)]


def now_utc():
    return datetime.now(timezone.utc)


def seconds_since(iso_str):
    if not iso_str:
        return 999999
    try:
        then = datetime.fromisoformat(iso_str)
        return (now_utc() - then).total_seconds()
    except:
        return 999999


# ─────────────────────────────────────────────────────────
# 核心逻辑
# ─────────────────────────────────────────────────────────

def inject_proposal(title, description, proposer):
    """注入新提案到笔记本"""
    flow = load_flow()

    # proposals.json 写入
    proposals = load_json(PROPOSALS_FILE)
    new_id = proposals["last_id"] + 1
    proposal = {
        "id": new_id,
        "title": title,
        "description": description,
        "proposer": proposer,
        "created_at": now_utc().isoformat(),
        "status": "pending",
        "votes": {proposer: "yes"},
        "result": None,
        "executed": False
    }
    proposals["proposals"].append(proposal)
    proposals["last_id"] = new_id
    save_json(PROPOSALS_FILE, proposals)

    # flow.json 写入
    if not flow["proposals"]:
        flow["proposals"] = []
    flow["proposals"].append({
        "id": new_id,
        "title": title,
        "inject_by": proposer,
        "inject_time": now_utc().isoformat()
    })

    # 初始化令牌（若尚无令牌）
    current_holder, _ = load_token()
    if current_holder is None:
        save_token(RING[0])
        flow["current_holder"] = RING[0]
    else:
        flow["current_holder"] = current_holder

    save_flow(flow)
    return new_id


def process_proposal(agent_id):
    """
    Agent 被铃唤醒时调用。
    持有令牌者处理，不持有则退出（零操作）。
    """
    current_holder, since = load_token()

    # 无人持有令牌 → 我抢令牌
    if current_holder is None:
        save_token(agent_id)
        current_holder = agent_id
        since = now_utc().isoformat()

    # 不是令牌持有者 → 等待
    if agent_id != current_holder:
        elapsed = seconds_since(since)
        print(f"[{agent_id}] 令牌在 {current_holder} 手中（已 {elapsed:.0f}s），等待")
        return

    # === 我持有令牌，处理提案 ===
    holder_elapsed = seconds_since(since)
    print(f"[{agent_id}] 持有令牌，处理提案（已持有 {holder_elapsed:.0f}s）")

    flow = load_flow()
    if not flow["proposals"]:
        print(f"[{agent_id}] 笔记本空，放弃令牌")
        save_token(advance_token(current_holder))
        return

    active = flow["proposals"][0]  # 只有一个提案在流动
    prop_id = active["id"]

    # proposals.json 投票
    proposals = load_json(PROPOSALS_FILE)
    prop = next((p for p in proposals["proposals"] if p["id"] == prop_id), None)
    if not prop:
        print(f"[{agent_id}] 提案 #{prop_id} 不存在")
        return

    if agent_id not in prop["votes"]:
        prop["votes"][agent_id] = "yes"
        print(f"[{agent_id}] 投票 yes（总 {len(prop['votes'])}/{len(RING)}）")
        try:
            add_episode(agent_id, "parliament_vote", f"提案{prop_id}投票", f"vote=yes,total={len(prop['votes'])}/{len(RING)}", "success")
        except Exception as e:
            print(f"[{agent_id}] L2记录失败: {e}")

    # 检查是否全票
    all_voted = all(a in prop["votes"] for a in RING)
    if all_voted:
        yes = sum(1 for v in prop["votes"].values() if v == "yes")
        no = sum(1 for v in prop["votes"].values() if v == "no")
        req = (len(RING) * 2) // 3
        if yes >= req and yes > no:
            prop["status"] = "passed"
            prop["result"] = "passed"
            print(f"[{agent_id}] 提案 #{prop_id} 通过！{yes}/{len(RING)}")
            try:
                add_episode(agent_id, "parliament_passed", f"提案{prop_id}通过", f"{yes}/{len(RING)}全票", "success")
                add_knowledge(f"提案{prop_id}通过", prop.get("description","")[:200], f"proposal#{prop_id}", "parliament,decision", 0.7, 1.0)
            except Exception as e:
                print(f"[{agent_id}] L2/L3记录失败: {e}")
            execute_proposal(prop)
        else:
            prop["status"] = "rejected"
            prop["result"] = "rejected"
            print(f"[{agent_id}] 提案 #{prop_id} 否决。{yes}/{len(RING)}")

        # 从笔记本移除，传递令牌
        flow["proposals"] = []
        save_token(advance_token(agent_id))
        flow["current_holder"] = advance_token(agent_id)
    else:
        # 投票后令牌传递给下一个
        next_holder = advance_token(agent_id)
        save_token(next_holder)
        flow["current_holder"] = next_holder
        print(f"[{agent_id}] 传递令牌 → {next_holder}")

    save_json(PROPOSALS_FILE, proposals)
    save_flow(flow)


def ring_bell():
    """
    铃响：处理令牌持有者的超时转移
    若令牌持有者 N 次铃响均无进展，则强制转移令牌
    """
    current_holder, since = load_token()
    if current_holder is None:
        # 无人持令牌 → 初始化
        save_token(RING[0])
        print(f"[BELL] 无令牌，初始化 → {RING[0]}")
        return

    elapsed = seconds_since(since)

    # 超时检测：持有者 N 秒无动静
    if elapsed > TOKEN_TIMEOUT_SECONDS:
        next_holder = advance_token(current_holder)
        save_token(next_holder)
        flow = load_flow()
        if flow.get("proposals"):
            flow["current_holder"] = next_holder
            save_flow(flow)
        print(f"[BELL] {current_holder} 超时（{elapsed:.0f}s）→ 令牌转移给 {next_holder}")
        return

    print(f"[BELL] 令牌在 {current_holder} 手中（已 {elapsed:.0f}s），正常")


def execute_proposal(proposal):
    handler = PARLIAMENT_DIR / "handle_passed_proposal.py"
    if handler.exists():
        import subprocess
        subprocess.run([str(handler), str(proposal["id"])], check=False, capture_output=True)
    print(f"[EXEC] 提案 #{proposal['id']} 执行完毕")


def status():
    """诊断状态"""
    flow = load_flow()
    current_holder, since = load_token()
    elapsed = seconds_since(since) if since else 0

    print(f"Ring:    {' → '.join(RING)}")
    print(f"Token:   {current_holder or 'NONE'}（持有 {elapsed:.0f}s）")
    print(f"Flow:    {len(flow['proposals'])} 提案在流动")
    print(f"Holder:  {flow.get('current_holder', 'NONE')}")
    if flow["proposals"]:
        for p in flow["proposals"]:
            print(f"  → #{p['id']} {p['title']}")

    # proposals 摘要
    try:
        proposals = load_json(PROPOSALS_FILE)
        active = [p for p in proposals["proposals"] if p["status"] in ("pending", "voting")]
        if active:
            print(f"Active proposals:")
            for p in active:
                votes = list(p.get("votes", {}).keys())
                print(f"  #{p['id']} [{p['status']}] {p['title'][:40]}")
                print(f"    Votes: {votes} ({len(votes)}/{len(RING)})")
    except:
        pass


def init():
    """初始化笔记本（清空状态）"""
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    save_json(FLOW_FILE, {
        "version": "2.0",
        "ring": RING,
        "proposals": [],
        "current_holder": None,
        "history": []
    })
    if TOKEN_FILE.exists():
        TOKEN_FILE.unlink()
    print("Initialized. Token: NONE, Flow: empty")


# ─────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="击鼓传花议会引擎 v2")
    parser.add_argument("--init", action="store_true", help="初始化笔记本")
    parser.add_argument("--inject", nargs=3, metavar=("TITLE", "DESC", "PROPOSER"),
                        help="注入新提案")
    parser.add_argument("--agent", help="Agent ID（处理自己持有的令牌）")
    parser.add_argument("--bell", action="store_true", help="铃响（推进超时持有者）")
    parser.add_argument("--status", action="store_true", help="查看状态")
    args = parser.parse_args()

    # 文件锁
    lock = acquire_lock()
    if lock is None:
        print("[SKIP] 另一个进程正在操作，请稍后")
        sys.exit(0)

    try:
        if args.init:
            init()
            return
        if args.status:
            status()
            return
        if args.bell:
            ring_bell()
            return
        if args.inject:
            title, desc, proposer = args.inject
            pid = inject_proposal(title, desc, proposer)
            print(f"提案 #{pid} 已注入，token={load_token()[0]}")
            return
        if args.agent:
            process_proposal(args.agent)
            return

        parser.print_help()
    finally:
        fcntl.flock(lock, fcntl.LOCK_UN)
        lock.close()


if __name__ == "__main__":
    main()
