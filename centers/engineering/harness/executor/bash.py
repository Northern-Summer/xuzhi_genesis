"""
Bash 执行器 - Phase 3
核心: 本地命令执行 + 安全守卫集成
"""

from __future__ import annotations

import asyncio
import logging
import os
import shlex
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger("executor.bash")


# ============================================================================
# 配置
# ============================================================================

@dataclass
class BashConfig:
    """Bash 执行配置"""
    timeout: int = 30                 # 默认超时(秒)
    max_output_chars: int = 50000    # 最大输出字符
    working_dir: str | None = None    # 工作目录
    env: dict[str, str] | None = field(default_factory=dict)  # 环境变量
    
    # 安全
    allowed_commands: list[str] | None = None  # 白名单命令
    blocked_commands: list[str] = field(default_factory=lambda: ["rm -rf /", ":(){:|:&};:", "dd if="])
    
    # 沙箱
    sandbox_enabled: bool = False     # 是否启用沙箱
    sandbox_dir: str | None = None    # 沙箱目录


@dataclass
class BashResult:
    """Bash 执行结果"""
    command: str
    returncode: int
    stdout: str
    stderr: str
    duration: float
    truncated: bool = False
    error: str | None = None
    
    @property
    def output(self) -> str:
        """合并 stdout + stderr"""
        parts = []
        if self.stdout:
            parts.append(self.stdout)
        if self.stderr:
            parts.append(self.stderr)
        return "\n".join(parts)
    
    @property
    def success(self) -> bool:
        return self.returncode == 0 and self.error is None
    
    def to_dict(self) -> dict:
        return {
            "command": self.command,
            "returncode": self.returncode,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "duration": f"{self.duration:.2f}s",
            "truncated": self.truncated,
            "error": self.error,
        }


# ============================================================================
# 危险命令检测
# ============================================================================

BLOCKED_PATTERNS = [
    r"rm\s+-rf\s+/",           # rm -rf /
    r"rm\s+-rf\s+\*",           # rm -rf *
    r":\(\)\{.*:\|.*&.*\};",    # Fork bomb
    r"dd\s+if=",                # Direct disk read
    r">\s*/dev/sd",             # Write to disk device
    r"chmod\s+-R\s+777\s+/",    # 777整个系统
    r"wget\s+.*\|\s*sh",        # Pipe to shell
    r"curl\s+.*\|\s*sh",        # Pipe to shell
    r"eval\s+\$",               # Eval variable
    r"exec\s+",                 # Exec
]

BLOCKED_PATTERNS_COMPILED = [(__import__('re').compile(p), p) for p in BLOCKED_PATTERNS]


def is_dangerous(command: str) -> tuple[bool, str]:
    """检测危险命令"""
    for pattern, original in BLOCKED_PATTERNS_COMPILED:
        if pattern.search(command):
            return True, f"Blocked pattern: {original}"
    return False, ""


# ============================================================================
# Bash 执行器
# ============================================================================

class BashExecutor:
    """
    Bash 命令执行器
    
    Features:
    - 异步执行
    - 超时控制
    - 输出截断
    - 危险命令检测
    - 沙箱隔离 (可选)
    """
    
    def __init__(self, config: BashConfig | None = None):
        self.config = config or BashConfig()
        self._logger = logger
    
    def execute(self, command: str, **kwargs) -> BashResult:
        """
        同步执行单条命令
        
        Args:
            command: 要执行的命令
            **kwargs: 覆盖默认配置
            
        Returns:
            BashResult
        """
        return asyncio.get_event_loop().run_until_complete(
            self.execute_async(command, **kwargs)
        )
    
    async def execute_async(self, command: str, **kwargs) -> BashResult:
        """
        异步执行单条命令
        """
        config = {**self.config.__dict__, **kwargs}
        timeout = config.get("timeout", self.config.timeout)
        
        # 危险命令检测
        is_danger, reason = is_dangerous(command)
        if is_danger:
            self._logger.warning(f"Dangerous command blocked: {reason}")
            return BashResult(
                command=command,
                returncode=1,
                stdout="",
                stderr=f"Command blocked: {reason}",
                duration=0,
                error=reason,
            )
        
        # 准备环境
        env = os.environ.copy()
        if config.get("env"):
            env.update(config["env"])
        
        cwd = config.get("working_dir") or self.config.working_dir or os.getcwd()
        
        # 创建临时目录作为沙箱
        sandbox_dir = None
        if config.get("sandbox_enabled"):
            sandbox_dir = tempfile.mkdtemp(prefix="harness_sandbox_")
            cwd = sandbox_dir
            self._logger.debug(f"Using sandbox: {sandbox_dir}")
        
        try:
            # 执行命令
            start_time = asyncio.get_event_loop().time()
            
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                env=env,
            )
            
            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                duration = asyncio.get_event_loop().time() - start_time
                return BashResult(
                    command=command,
                    returncode=124,  # Timeout exit code
                    stdout="",
                    stderr=f"Command timed out after {timeout}s",
                    duration=duration,
                    error="timeout",
                )
            
            duration = asyncio.get_event_loop().time() - start_time
            
            stdout = stdout_bytes.decode("utf-8", errors="replace")
            stderr = stderr_bytes.decode("utf-8", errors="replace")
            
            # 截断输出
            max_chars = config.get("max_output_chars", self.config.max_output_chars)
            truncated = False
            if len(stdout) > max_chars:
                stdout = stdout[:max_chars] + f"\n\n[OUTPUT TRUNCATED: {len(stdout) - max_chars} chars removed]"
                truncated = True
            if len(stderr) > max_chars // 4:  # stderr 更严格
                stderr = stderr[:max_chars // 4] + f"\n[STDERR TRUNCATED]"
                truncated = True
            
            return BashResult(
                command=command,
                returncode=process.returncode,
                stdout=stdout,
                stderr=stderr,
                duration=duration,
                truncated=truncated,
            )
            
        except Exception as e:
            duration = asyncio.get_event_loop().time() - start_time
            self._logger.error(f"Execution error: {e}")
            return BashResult(
                command=command,
                returncode=1,
                stdout="",
                stderr=str(e),
                duration=duration,
                error=str(e),
            )
        
        finally:
            # 清理沙箱
            if sandbox_dir and os.path.exists(sandbox_dir):
                import shutil
                shutil.rmtree(sandbox_dir, ignore_errors=True)
    
    def execute_batch(self, commands: list[str], **kwargs) -> list[BashResult]:
        """批量执行命令"""
        results = []
        for cmd in commands:
            result = self.execute(cmd, **kwargs)
            results.append(result)
            # 如果命令失败，停止执行
            if not result.success:
                self._logger.warning(f"Command failed, stopping batch: {cmd}")
                break
        return results


# ============================================================================
# 便捷函数
# ============================================================================

_default_executor: BashExecutor | None = None


def get_executor() -> BashExecutor:
    """获取默认执行器"""
    global _default_executor
    if _default_executor is None:
        _default_executor = BashExecutor()
    return _default_executor


def execute(command: str, **kwargs) -> BashResult:
    """快捷执行函数"""
    return get_executor().execute(command, **kwargs)


def execute_batch(commands: list[str], **kwargs) -> list[BashResult]:
    """快捷批量执行函数"""
    return get_executor().execute_batch(commands, **kwargs)
