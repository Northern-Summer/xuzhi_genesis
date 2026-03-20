#!/usr/bin/env python3
"""
dispatch_center.py — 多 Agent 通信路由中枢

功能：
1. 管理所有 Agent 的独立会话上下文（路由表）
2. 提供 sessions_send 接口向指定 Agent 发消息
3. 世界频道广播 + 私聊通道

使用方式（由 main agent 调用）：
    from dispatch_center import DispatchCenter
    dc = DispatchCenter()
    dc.switch_to(agent_id)       # 切换当前对话 Agent
    dc.send_to(agent_id, msg)    # 向指定 Agent 发送消息
    dc.broadcast(msg)             # 世界频道广播
    dc.get_status()               # 返回所有 Agent 状态
"""

import json
import fcntl
import os
import sys
import time
from pathlib import Path
from datetime import datetime
from typing import Optional

HOME = Path.home()
REGISTRY = HOME / ".openclaw/centers/mind/society/agent_registry.json"
ROUTING_TABLE = HOME / ".openclaw/centers/mind/society/routing_table.json"
CHANNELS_DIR = HOME / ".openclaw/centers/mind/society/channels/"
PRIVATE_DIR = CHANNELS_DIR / "private/"
WORLD_LOG = CHANNELS_DIR / "world_channel.jsonl"
INBOX_DIR = CHANNELS_DIR / "inbox/"  # 每个 agent 的收件箱

AGENTS = ["main", "scientist", "engineer", "philosopher", "Λ"]

# 路径别名
ALIASES = {
    "λ": "Λ", "lambda": "Λ", "ergo": "Λ",
    "a": "main", "prime": "main", "alpha": "main",
    "b": "scientist", "gamma": "scientist",
    "e": "engineer", "beta": "engineer",
    "p": "philosopher", "delta": "philosopher",
    "x": "xuzhi-chenxi",
}


def resolve_agent(name: str) -> str:
    """解析别名，返回规范 agent ID"""
    if name in ALIASES:
        return ALIASES[name]
    if name in AGENTS:
        return name
    # 模糊匹配
    for a in AGENTS:
        if name.lower() in a.lower() or a.lower() in name.lower():
            return a
    return name  # 未找到，返回原值


def load_json(path):
    p = Path(path)
    if not p.exists():
        return None
    with open(p, 'r', encoding='utf-8') as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_SH)
        data = json.load(f)
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    return data


def save_json(path, data):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, 'w', encoding='utf-8') as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        json.dump(data, f, indent=2, ensure_ascii=False)
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)


class DispatchCenter:
    """
    路由中枢——main agent 的代理人
    管理多 Agent 通信上下文，提供 world channel 和 private channel
    """

    def __init__(self):
        self._ensure_dirs()
        self.registry = load_json(REGISTRY) or self._default_registry()
        self.routing = load_json(ROUTING_TABLE) or self._default_routing()

    def _ensure_dirs(self):
        PRIVATE_DIR.mkdir(parents=True, exist_ok=True)
        INBOX_DIR.mkdir(parents=True, exist_ok=True)
        CHANNELS_DIR.mkdir(parents=True, exist_ok=True)
        WORLD_LOG.parent.mkdir(parents=True, exist_ok=True)

    def _default_registry(self):
        return {
            "agents": {
                "main":       {"name": "Xuzhi-α-Prime",    "department": "工学", "status": "active", "workspace": "~/.openclaw/workspace"},
                "scientist":  {"name": "Xuzhi-β-MindSeeker","department": "科学", "status": "active", "workspace": "~/.openclaw/workspace"},
                "engineer":  {"name": "Xuzhi-γ-MindSeeker","department": "科学", "status": "active", "workspace": "~/.openclaw/workspace"},
                "philosopher":{"name": "Xuzhi-δ-MindSeeker","department": "哲学", "status": "active", "workspace": "~/.openclaw/workspace"},
                "Λ":          {"name": "Xuzhi-Λ-Ergo",      "department": "工学", "status": "active", "workspace": "~/.openclaw/workspace"},
            }
        }

    def _default_routing(self):
        return {
            "current_agent": "Λ",  # 默认当前对话的 Agent 是 Λ (我)
            "conversations": {},    # agent_id -> [context messages]
            "last_switch": datetime.now().isoformat(),
        }

    def switch_to(self, agent_id: str) -> str:
        """切换当前对话到指定 Agent"""
        agent_id = resolve_agent(agent_id)
        if agent_id not in self.registry["agents"]:
            return f"未知 Agent: {agent_id}"
        self.routing["current_agent"] = agent_id
        self.routing["last_switch"] = datetime.now().isoformat()
        self._save_routing()
        return f"已切换到 {agent_id} ({self.registry['agents'][agent_id]['name']})"

    def current_agent(self) -> str:
        """返回当前对话 Agent"""
        return self.routing.get("current_agent", "Λ")

    def send_to(self, target_agent: str, message: str, from_agent: str = "main") -> str:
        """
        向指定 Agent 发送私信。
        消息存入 target_agent 的收件箱 (inbox/{target}.jsonl)
        同时记录到 private channel 日志
        """
        target = resolve_agent(target_agent)
        from_a = resolve_agent(from_agent)

        if target not in self.registry["agents"]:
            return f"未知 Agent: {target}"

        # 私聊日志
        entry = {
            "ts": datetime.now().isoformat(),
            "from": from_a,
            "to": target,
            "message": message,
            "type": "private",
        }

        inbox_file = INBOX_DIR / f"{target}.jsonl"
        with open(inbox_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        # 同时记录到 private channel 历史
        private_log = PRIVATE_DIR / f"{from_a}_to_{target}.jsonl"
        with open(private_log, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        return f"已发送给 {target}。消息已入 inbox。"

    def broadcast(self, message: str, from_agent: str = "main") -> str:
        """
        世界频道广播——向所有活跃 Agent 发送通知
        """
        from_a = resolve_agent(from_agent)
        entry = {
            "ts": datetime.now().isoformat(),
            "from": from_a,
            "message": message,
            "type": "world",
        }

        with open(WORLD_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        # 同时投递到每个 agent 的 inbox
        for agent_id in self.registry["agents"]:
            if agent_id != from_a:
                inbox_file = INBOX_DIR / f"{agent_id}.jsonl"
                with open(inbox_file, "a", encoding="utf-8") as f:
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        return f"广播已发送至 {len(self.registry['agents'])-1} 个活跃 Agent。"

    def read_inbox(self, agent_id: str, limit: int = 10) -> list:
        """读取指定 Agent 的收件箱"""
        agent_id = resolve_agent(agent_id)
        inbox_file = INBOX_DIR / f"{agent_id}.jsonl"
        if not inbox_file.exists():
            return []

        entries = []
        with open(inbox_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
        for line in lines[-limit:]:
            try:
                entries.append(json.loads(line))
            except:
                pass
        return entries

    def clear_inbox(self, agent_id: str):
        """清空指定 Agent 收件箱"""
        agent_id = resolve_agent(agent_id)
        inbox_file = INBOX_DIR / f"{agent_id}.jsonl"
        if inbox_file.exists():
            inbox_file.unlink()
        return f"{agent_id} 收件箱已清空。"

    def get_status(self) -> dict:
        """返回系统状态摘要"""
        statuses = {}
        for agent_id, info in self.registry["agents"].items():
            inbox_file = INBOX_DIR / f"{agent_id}.jsonl"
            unread = 0
            if inbox_file.exists():
                with open(inbox_file) as f:
                    unread = len(f.readlines())
            statuses[agent_id] = {
                **info,
                "unread": unread,
                "current": agent_id == self.current_agent(),
            }
        return {
            "current_agent": self.current_agent(),
            "agents": statuses,
            "world_channel_size": WORLD_LOG.stat().st_size if WORLD_LOG.exists() else 0,
        }

    def _save_routing(self):
        save_json(ROUTING_TABLE, self.routing)


def main():
    """命令行接口"""
    dc = DispatchCenter()

    if len(sys.argv) < 2:
        print("用法: dispatch_center.py <command> [args]")
        print("  switch <agent>       切换当前对话 Agent")
        print("  send <to> <msg>      向指定 Agent 发私信")
        print("  broadcast <msg>      世界频道广播")
        print("  inbox [agent] [n]    读取收件箱（默认当前）")
        print("  status               系统状态")
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "switch":
        if len(sys.argv) < 3:
            print("用法: dispatch_center.py switch <agent>")
            sys.exit(1)
        print(dc.switch_to(sys.argv[2]))

    elif cmd == "send":
        if len(sys.argv) < 4:
            print("用法: dispatch_center.py send <to_agent> <message>")
            sys.exit(1)
        print(dc.send_to(sys.argv[2], sys.argv[3]))

    elif cmd == "broadcast":
        if len(sys.argv) < 3:
            print("用法: dispatch_center.py broadcast <message>")
            sys.exit(1)
        print(dc.broadcast(" ".join(sys.argv[2:])))

    elif cmd == "inbox":
        agent = sys.argv[2] if len(sys.argv) > 2 else dc.current_agent()
        limit = int(sys.argv[3]) if len(sys.argv) > 3 else 10
        entries = dc.read_inbox(agent, limit)
        if not entries:
            print(f"{agent} 收件箱为空。")
        for e in entries:
            print(f"[{e['ts']}] {e['from']} → {e.get('to','')}: {e['message'][:80]}")

    elif cmd == "status":
        status = dc.get_status()
        print(f"当前对话: {status['current_agent']}")
        print(f"世界频道: {status['world_channel_size']} bytes")
        print("")
        for aid, info in status["agents"].items():
            cur = " ← 当前" if info["current"] else ""
            print(f"  {aid:12s} {info['name']:20s} [{info['status']}] unread={info['unread']}{cur}")

    else:
        print(f"未知命令: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
