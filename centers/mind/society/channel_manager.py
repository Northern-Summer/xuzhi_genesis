#!/usr/bin/env python3
"""
channel_manager.py — 智能体私聊 + 世界频道

架构：
- private/{from}_{to}.jsonl    — 两人私聊历史（双向各自一份）
- world_channel.jsonl          — 世界频道（全体可读）
- inbox/{agent}.jsonl          — 每个 agent 的收件箱（ dispatch_center.py 共用）

权限模型：
- 每个 agent 对自己的 inbox 有完全控制权
- 其他 agent 发送私信时，消息先入目标 inbox，由目标自行处理
- 世界频道任何 agent 可写，但需在 dispatch_center 注册

设计原则：
- 收件箱所有权 > 发送方——接收方可以拒绝、过滤
- 消息一旦入 inbox，发送方无法单方面撤回（接收方控制删除权）
"""

import json
import fcntl
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

HOME = Path.home()
CHANNELS_DIR = HOME / ".openclaw/centers/mind/society/channels/"
WORLD_LOG = CHANNELS_DIR / "world_channel.jsonl"
PRIVATE_DIR = CHANNELS_DIR / "private/"
INBOX_DIR = CHANNELS_DIR / "inbox/"


def ensure_dirs():
    PRIVATE_DIR.mkdir(parents=True, exist_ok=True)
    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    WORLD_LOG.parent.mkdir(parents=True, exist_ok=True)


def private_log_path(from_a: str, to_a: str) -> Path:
    """私聊日志路径（按字母序确保唯一路径）"""
    a, b = sorted([from_a, to_a])
    return PRIVATE_DIR / f"{a}_and_{b}.jsonl"


def append_jsonl(path: Path, entry: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def read_jsonl(path: Path, limit: int = 50) -> list:
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    return [json.loads(l) for l in lines[-limit:]]


def delete_jsonl_entries(path: Path, keep_last_n: int = 0):
    """截断 JSONL 文件，保留最后 keep_last_n 行"""
    if not path.exists():
        return
    with open(path, "r") as f:
        lines = f.readlines()
    with open(path, "w") as f:
        f.writlines(lines[-keep_last_n:])


class ChannelManager:
    """
    私聊 + 世界频道管理器
    每个 agent 操作时以自己的 agent_id 为准
    """

    def __init__(self, my_agent_id: str):
        self.my_id = my_agent_id
        ensure_dirs()

    # ── 世界频道 ────────────────────────────────────────────

    def world_broadcast(self, message: str) -> str:
        """向世界频道发送广播（所有 agent 可见）"""
        entry = {
            "ts": datetime.now().isoformat(),
            "from": self.my_id,
            "type": "world",
            "message": message,
        }
        append_jsonl(WORLD_LOG, entry)
        return f"广播已发布至世界频道。[{len(message)} chars]"

    def world_timeline(self, limit: int = 20) -> list:
        """查看世界频道最新消息"""
        return read_jsonl(WORLD_LOG, limit)

    # ── 私聊 ────────────────────────────────────────────────

    def private_message(self, to_agent: str, message: str) -> str:
        """向指定 agent 发送私信"""
        entry = {
            "ts": datetime.now().isoformat(),
            "from": self.my_id,
            "to": to_agent,
            "type": "private",
            "message": message,
        }
        # 双方各自的私聊日志（对称）
        log_a = private_log_path(self.my_id, to_agent)
        append_jsonl(log_a, entry)
        # 入目标 inbox
        inbox_file = INBOX_DIR / f"{to_agent}.jsonl"
        append_jsonl(inbox_file, entry)
        return f"私信已发送给 {to_agent}。"

    def private_history(self, with_agent: str, limit: int = 50) -> list:
        """查看与某 agent 的私聊历史"""
        log = private_log_path(self.my_id, with_agent)
        return read_jsonl(log, limit)

    def private_delete_message(self, with_agent: str, ts: str):
        """撤回指定时间戳的私聊消息（仅自己能删除自己的消息）"""
        log = private_log_path(self.my_id, with_agent)
        if not log.exists():
            return "无历史记录。"

        lines = []
        with open(log, "r") as f:
            lines = f.readlines()

        new_lines = []
        for line in lines:
            entry = json.loads(line)
            # 只删除自己发的、匹配时间戳的消息
            if not (entry["from"] == self.my_id and entry["ts"] == ts):
                new_lines.append(line)

        with open(log, "w") as f:
            f.writelines(new_lines)

        return f"已撤回 {ts} 的消息。"

    # ── 收件箱 ──────────────────────────────────────────────

    def inbox(self, limit: int = 20) -> list:
        """查看自己的收件箱（所有发给自己的消息）"""
        inbox_file = INBOX_DIR / f"{self.my_id}.jsonl"
        return read_jsonl(inbox_file, limit)

    def inbox_count(self) -> int:
        inbox_file = INBOX_DIR / f"{self.my_id}.jsonl"
        if not inbox_file.exists():
            return 0
        with open(inbox_file) as f:
            return len(f.readlines())

    def inbox_delete(self, ts: str):
        """从收件箱删除指定消息（自己控制）"""
        inbox_file = INBOX_DIR / f"{self.my_id}.jsonl"
        if not inbox_file.exists():
            return "收件箱为空。"

        lines = []
        with open(inbox_file, "r") as f:
            lines = f.readlines()

        new_lines = [l for l in lines if json.loads(l)["ts"] != ts]
        with open(inbox_file, "w") as f:
            f.writelines(new_lines)

        return f"已从收件箱删除 {ts}。"

    def inbox_clear(self):
        """清空收件箱"""
        inbox_file = INBOX_DIR / f"{self.my_id}.jsonl"
        if inbox_file.exists():
            inbox_file.unlink()
        return "收件箱已清空。"

    # ── 摘要 ────────────────────────────────────────────────

    def summary(self) -> dict:
        """返回频道状态摘要"""
        unread = self.inbox_count()
        world_size = WORLD_LOG.stat().st_size if WORLD_LOG.exists() else 0

        private_peers = []
        if PRIVATE_DIR.exists():
            for f in PRIVATE_DIR.iterdir():
                if f"{self.my_id}_" in f.name or f"_and_{self.my_id}" in f.name:
                    peer = f.stem.replace(f"{self.my_id}_and_", "").replace(f"{self.my_id}_", "").replace("_and_", "")
                    private_peers.append(peer)

        return {
            "my_id": self.my_id,
            "unread_inbox": unread,
            "world_channel_bytes": world_size,
            "private_chats_with": private_peers,
        }


def main():
    if len(sys.argv) < 3:
        print("用法: channel_manager.py <my_agent_id> <command> [args]")
        print("  world_broadcast <msg>         世界频道广播")
        print("  world_timeline [n]           查看世界频道")
        print("  private <to> <msg>           发送私信")
        print("  history <with> [n]           私聊历史")
        print("  inbox [n]                    收件箱")
        print("  inbox_clear                  清空收件箱")
        print("  summary                      频道摘要")
        sys.exit(0)

    my_id = sys.argv[1]
    cmd = sys.argv[2]
    cm = ChannelManager(my_id)

    if cmd == "world_broadcast":
        print(cm.world_broadcast(" ".join(sys.argv[3:])))

    elif cmd == "world_timeline":
        limit = int(sys.argv[3]) if len(sys.argv) > 3 else 20
        for entry in cm.world_timeline(limit):
            print(f"[{entry['ts']}] {entry['from']}: {entry['message'][:100]}")

    elif cmd == "private":
        if len(sys.argv) < 5:
            print("用法: channel_manager.py <my_id> private <to> <msg>")
            sys.exit(1)
        print(cm.private_message(sys.argv[3], sys.argv[4]))

    elif cmd == "history":
        peer = sys.argv[3] if len(sys.argv) > 3 else None
        limit = int(sys.argv[4]) if len(sys.argv) > 4 else 50
        if not peer:
            print("用法: channel_manager.py <my_id> history <with>")
            sys.exit(1)
        for entry in cm.private_history(peer, limit):
            print(f"[{entry['ts']}] {entry['from']} → {entry['to']}: {entry['message'][:100]}")

    elif cmd == "inbox":
        limit = int(sys.argv[3]) if len(sys.argv) > 3 else 20
        for entry in cm.inbox(limit):
            print(f"[{entry['ts']}] {entry['from']} → {entry.get('to','')} [{entry['type']}]: {entry['message'][:100]}")

    elif cmd == "inbox_clear":
        print(cm.inbox_clear())

    elif cmd == "summary":
        s = cm.summary()
        print(f"Agent: {s['my_id']}")
        print(f"收件箱未读: {s['unread_inbox']}")
        print(f"世界频道: {s['world_channel_bytes']} bytes")
        print(f"私聊对象: {s['private_chats_with']}")

    else:
        print(f"未知命令: {cmd}")


if __name__ == "__main__":
    main()
