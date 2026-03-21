"""
checkpoint.py — 任务断点续跑基础设施
=====================================
所有Agent共享的 checkpoint/resume 引擎

核心设计：
- 每个Agent维护自己的检查点文件（workspace独立）
- 启动时调用 resume_or_start() 自动判断：恢复中断 or 新任务
- 长时间任务：step_checkpoint() 分段保存进度
- 外部watchdog通过检查点文件感知Agent是否存活

断点判断逻辑（核心）：
  t=0h    新任务开始，save_checkpoint(status=running)
  t=0.5h  step_checkpoint() 保存第3步
  t=1.5h  [Gateway崩溃] 进程中断，状态仍=running
  t=2.0h  [自动唤醒] resume_or_start() 发现 checkpoint 且 age<3h
          → 判定为中断，resume 从 step=3 继续
  t=4.0h  cron再次触发，resume_or_start() 发现已完成，skip

时间窗口设置理由：
  - 正常任务 <4h（cron周期）
  - 超过3h的running状态 = 必定中断，可安全恢复
"""

from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Any, Optional
from enum import Enum


# ============================================================================
# 核心数据模型
# ============================================================================

class TaskStatus(Enum):
    PENDING = "pending"       # 任务已创建，未开始
    RUNNING = "running"       # 任务执行中
    STEPPING = "stepping"     # 任务执行中，已保存分步进度
    COMPLETED = "completed"   # 任务正常完成
    FAILED = "failed"         # 任务失败（可重试）
    ABANDONED = "abandoned"   # 任务被中断，已放弃


@dataclass
class Task:
    task_id: str
    agent_id: str
    task_type: str            # e.g. "autorra_research", "health_scan"
    description: str
    status: TaskStatus = TaskStatus.PENDING
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    
    # 分步进度
    current_step: int = 0
    total_steps: int = 1
    step_label: str = ""
    
    # 上下文（用于resume）
    context: dict[str, Any] = field(default_factory=dict)
    
    # 元数据
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Checkpoint:
    """检查点文件结构"""
    version: str = "1.0"
    agent_id: str
    current_task: Optional[Task] = None
    completed_tasks: list[dict] = field(default_factory=list)
    heartbeat_at: float = field(default_factory=time.time)
    crashed_at: Optional[float] = None


# ============================================================================
# 检查点引擎
# ============================================================================

class CheckpointEngine:
    """
    断点续跑引擎 — 每个Agent一个实例
    使用agent专属workspace作为存储位置
    """
    
    def __init__(self, agent_id: str, workspace: str):
        self.agent_id = agent_id
        self.workspace = Path(workspace)
        self.checkpoint_file = self.workspace / ".checkpoint.json"
        self._lock_file = self.workspace / ".checkpoint.lock"
        
        # 时间窗口：超过此时间未更新 = 可判定为中断（秒）
        self.STALE_THRESHOLD = 3 * 3600  # 3小时
        self.HEARTBEAT_INTERVAL = 300     # 5分钟心跳
    
    # --------------------------------------------------------------------------
    # 核心API
    # --------------------------------------------------------------------------
    
    def resume_or_start(self, task_type: str, description: str,
                        total_steps: int = 1, context: dict = None) -> tuple[str, bool]:
        """
        每次Agent启动时调用此函数。
        
        Returns:
            (task_id, is_resuming): 
                is_resume=True → 恢复中断任务
                is_resume=False → 开始新任务
        """
        cp = self._load()
        now = time.time()
        
        if cp and cp.current_task:
            age = now - cp.heartbeat_at
            
            if age < self.STALE_THRESHOLD and cp.current_task.status in (
                TaskStatus.RUNNING, TaskStatus.STEPPING
            ):
                # 判定：任务中断，需恢复
                task_id = cp.current_task.task_id
                cp.current_task.status = TaskStatus.RUNNING
                cp.current_task.updated_at = now
                cp.heartbeat_at = now
                self._save(cp)
                
                print(f"[checkpoint] ✓ 恢复中断任务 {task_id}（中断于 step={cp.current_task.current_step}，已中断 {int(age/60)}min）", 
                      file=__import__('sys').stderr)
                return task_id, True
            
            elif age >= self.STALE_THRESHOLD and cp.current_task.status in (
                TaskStatus.RUNNING, TaskStatus.STEPPING
            ):
                # 任务超时，标记为放弃
                cp.current_task.status = TaskStatus.ABANDONED
                cp.current_task.completed_at = now
                if cp.current_task:
                    cp.completed_tasks.append(asdict(cp.current_task))
                cp.current_task = None
                self._save(cp)
                print(f"[checkpoint] ⚠ 任务超时已标记放弃", file=__import__('sys').stderr)
        
        # 新任务
        task_id = f"{task_type}_{int(now)}_{uuid.uuid4().hex[:6]}"
        task = Task(
            task_id=task_id,
            agent_id=self.agent_id,
            task_type=task_type,
            description=description,
            status=TaskStatus.RUNNING,
            total_steps=total_steps,
            context=context or {}
        )
        cp = Checkpoint(agent_id=self.agent_id, current_task=task, heartbeat_at=now)
        self._save(cp)
        
        print(f"[checkpoint] ○ 新任务 {task_id}（{total_steps}步）", file=__import__('sys').stderr)
        return task_id, False
    
    def step_checkpoint(self, step: int, step_label: str = "", 
                        context_update: dict = None) -> None:
        """
        每个关键步骤完成后调用。
        保存当前进度，支持从断点恢复。
        """
        cp = self._load()
        if not cp or not cp.current_task:
            return
        
        cp.current_task.current_step = step
        cp.current_task.step_label = step_label
        cp.current_task.status = TaskStatus.STEPPING
        cp.current_task.updated_at = time.time()
        cp.heartbeat_at = time.time()
        
        if context_update:
            cp.current_task.context.update(context_update)
        
        self._save(cp)
        print(f"[checkpoint] ✓ Step {step}/{cp.current_task.total_steps}: {step_label}", 
              file=__import__('sys').stderr)
    
    def complete(self, result: Any = None) -> None:
        """任务正常完成"""
        cp = self._load()
        if not cp or not cp.current_task:
            return
        
        now = time.time()
        cp.current_task.status = TaskStatus.COMPLETED
        cp.current_task.completed_at = now
        cp.current_task.updated_at = now
        cp.heartbeat_at = now
        if result:
            cp.current_task.context["result"] = result
        
        # 移到已完成列表（保留最近10条）
        cp.completed_tasks.append(asdict(cp.current_task))
        cp.completed_tasks = cp.completed_tasks[-10:]
        
        cp.current_task = None
        self._save(cp)
        print(f"[checkpoint] ✓ 任务完成", file=__import__('sys').stderr)
    
    def fail(self, error: str = "") -> None:
        """任务失败"""
        cp = self._load()
        if not cp or not cp.current_task:
            return
        
        now = time.time()
        cp.current_task.status = TaskStatus.FAILED
        cp.current_task.completed_at = now
        cp.current_task.updated_at = now
        cp.current_task.context["error"] = error
        
        cp.completed_tasks.append(asdict(cp.current_task))
        cp.completed_tasks = cp.completed_tasks[-10:]
        
        cp.current_task = None
        self._save(cp)
        print(f"[checkpoint] ✗ 任务失败: {error}", file=__import__('sys').stderr)
    
    def heartbeat(self) -> None:
        """发送心跳（默认每5分钟由外部调用）"""
        cp = self._load()
        if cp and cp.current_task:
            cp.heartbeat_at = time.time()
            cp.current_task.updated_at = time.time()
            self._save(cp)
    
    def get_current_task(self) -> Optional[Task]:
        """获取当前任务（用于判断是否需要恢复）"""
        cp = self._load()
        return cp.current_task if cp else None
    
    def get_progress(self) -> dict:
        """获取当前进度摘要"""
        task = self.get_current_task()
        if not task:
            return {"status": "idle"}
        
        age = time.time() - task.updated_at
        return {
            "task_id": task.task_id,
            "task_type": task.task_type,
            "status": task.status.value,
            "step": f"{task.current_step}/{task.total_steps}",
            "step_label": task.step_label,
            "age_seconds": int(age),
            "is_stale": age > self.STALE_THRESHOLD
        }
    
    # --------------------------------------------------------------------------
    # 内部方法
    # --------------------------------------------------------------------------
    
    def _load(self) -> Optional[Checkpoint]:
        if not self.checkpoint_file.exists():
            return None
        try:
            with open(self.checkpoint_file) as f:
                data = json.load(f)
            
            cp = Checkpoint(agent_id=data.get("agent_id",""))
            if data.get("current_task"):
                t = data["current_task"]
                cp.current_task = Task(
                    task_id=t["task_id"], agent_id=t["agent_id"],
                    task_type=t["task_type"], description=t["description"],
                    status=TaskStatus(t.get("status","pending")),
                    created_at=t.get("created_at", time.time()),
                    updated_at=t.get("updated_at", time.time()),
                    completed_at=t.get("completed_at"),
                    current_step=t.get("current_step", 0),
                    total_steps=t.get("total_steps", 1),
                    step_label=t.get("step_label",""),
                    context=t.get("context", {}),
                    metadata=t.get("metadata", {})
                )
            cp.completed_tasks = data.get("completed_tasks", [])
            cp.heartbeat_at = data.get("heartbeat_at", time.time())
            cp.crashed_at = data.get("crashed_at")
            return cp
        except (json.JSONDecodeError, KeyError, FileNotFoundError):
            return None
    
    def _save(self, cp: Checkpoint) -> None:
        data = {
            "version": cp.version,
            "agent_id": cp.agent_id,
            "heartbeat_at": cp.heartbeat_at,
            "crashed_at": cp.crashed_at,
            "completed_tasks": cp.completed_tasks,
        }
        if cp.current_task:
            t = cp.current_task
            data["current_task"] = {
                "task_id": t.task_id, "agent_id": t.agent_id,
                "task_type": t.task_type, "description": t.description,
                "status": t.status.value,
                "created_at": t.created_at, "updated_at": t.updated_at,
                "completed_at": t.completed_at,
                "current_step": t.current_step, "total_steps": t.total_steps,
                "step_label": t.step_label,
                "context": t.context, "metadata": t.metadata
            }
        with open(self.checkpoint_file, "w") as f:
            json.dump(data, f, indent=2)
        # 同步fsync确保写入
        try:
            os.fsync(f.fileno())
        except:
            pass


# ============================================================================
# 全局快捷函数（用于cron/外部调用）
# ============================================================================

def get_agent_workspace(agent_id: str) -> str:
    """从agent_id推断workspace路径"""
    from pathlib import Path
    base = Path.home() / ".openclaw"
    
    # 标准映射
    mapping = {
        "main":                  "workspace",
        "xuzhi-researcher":      "workspace-xuzhi-researcher",
        "xuzhi-engineer":        "workspace-xuzhi-engineer",
        "xuzhi-philosopher":     "workspace-xuzhi-philosopher",
        "xuzhi-chenxi":          "workspace-xuzhi",
        "scientist":             "workspace-scientist",
        "engineer":              "workspace-engineer",
        "philosopher":           "workspace-philosopher",
    }
    ws_name = mapping.get(agent_id, f"workspace-{agent_id}")
    return str(base / ws_name)


def check_all_agents_status() -> dict[str, dict]:
    """
    全局健康检查：扫描所有Agent的检查点状态
    返回 {agent_id: status_dict}
    用于watchdog和系统面板
    """
    import subprocess
    result = {}
    
    # 获取所有注册的agent IDs
    try:
        out = subprocess.run(
            ["openclaw", "agents", "list"],
            capture_output=True, text=True, timeout=10
        )
        import re
        ids = re.findall(r'^\s*-\s+(\S+)', out.stdout, re.MULTILINE)
    except:
        ids = ["main", "xuzhi-researcher", "xuzhi-engineer", 
               "xuzhi-philosopher", "xuzhi-chenxi"]
    
    for agent_id in ids:
        ws = get_agent_workspace(agent_id)
        cp_file = Path(ws) / ".checkpoint.json"
        
        if not cp_file.exists():
            result[agent_id] = {"status": "no_checkpoint", "healthy": True}
            continue
        
        try:
            with open(cp_file) as f:
                data = json.load(f)
            
            task = data.get("current_task")
            heartbeat = data.get("heartbeat_at", 0)
            age = time.time() - heartbeat
            stale = age > 3 * 3600
            
            if task:
                result[agent_id] = {
                    "status": task.get("status", "unknown"),
                    "task_type": task.get("task_type", ""),
                    "step": f"{task.get('current_step',0)}/{task.get('total_steps',1)}",
                    "age_seconds": int(age),
                    "stale": stale,
                    "healthy": not stale and task.get("status") in ("running","stepping")
                }
            else:
                result[agent_id] = {"status": "idle", "age_seconds": int(age), "healthy": True}
        except:
            result[agent_id] = {"status": "error", "healthy": False}
    
    return result


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("用法: checkpoint.py <agent_id> [action] [args...]")
        print("  status <agent_id>      — 查看检查点状态")
        print("  list                   — 查看所有Agent状态")
        print("  demo                   — 演示resume_or_start")
        sys.exit(0)
    
    action = sys.argv[1]
    
    if action == "status":
        if len(sys.argv) < 3:
            print("需要 agent_id")
            sys.exit(1)
        agent_id = sys.argv[2]
        ws = get_agent_workspace(agent_id)
        eng = CheckpointEngine(agent_id, ws)
        prog = eng.get_progress()
        print(json.dumps(prog, indent=2))
    
    elif action == "list":
        all_status = check_all_agents_status()
        print(json.dumps(all_status, indent=2))
    
    elif action == "demo":
        # 演示
        agent_id = "test-agent"
        ws = "/tmp/test_checkpoint"
        import os; os.makedirs(ws, exist_ok=True)
        eng = CheckpointEngine(agent_id, ws)
        
        print("=== 场景1: 新任务 ===")
        tid, resuming = eng.resume_or_start("autorra", "AutoRA研究任务", total_steps=5)
        print(f"  task_id={tid}, resuming={resuming}")
        
        print("\n=== 场景2: 模拟中断后重启 ===")
        eng2 = CheckpointEngine(agent_id, ws)
        tid2, resuming2 = eng2.resume_or_start("autorra", "AutoRA研究任务", total_steps=5)
        print(f"  task_id={tid2}, resuming={resuming2}")
        print(f"  (应该是同一任务，因为状态文件还在)")
        
        eng2.step_checkpoint(3, "已完成文献调研")
        eng2.complete({"papers_found": 42})
        
        print("\n=== 场景3: 任务完成后新任务 ===")
        eng3 = CheckpointEngine(agent_id, ws)
        tid3, resuming3 = eng3.resume_or_start("autorra", "AutoRA研究任务", total_steps=5)
        print(f"  task_id={tid3}, resuming={resuming3}")
        
        import shutil; shutil.rmtree(ws, ignore_errors=True)
        print("\n✓ Demo完成")
