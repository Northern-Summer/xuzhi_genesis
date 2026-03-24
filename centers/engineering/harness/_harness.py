"""
Harness Agent - Phase 3 端到端集成
Phase 4 增强: 集成 ResourceMonitor + DynamicRouter
核心: 连接 Model + Executor + Loop + Monitor + Router
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from core.model import ModelConfig, LitellmModel, CostStats
from core.retry import LoopConfig, LoopStats, LoopInterrupt, StepLimitExceeded, CostLimitExceeded
from executor.bash import BashExecutor, BashConfig
from context.optimized_cache import OptimizedCache, OptimizedCacheConfig
from monitor.resource_monitor import ResourceMonitor, get_monitor, SystemStatus
from router.dynamic_router import DynamicRouter, Task, TaskType, RoutingStrategy, get_router

logger = logging.getLogger("harness")


# ============================================================================
# 配置
# ============================================================================

@dataclass
class HarnessConfig:
    """Harness Agent 配置"""
    # 模型
    model: ModelConfig = field(default_factory=lambda: ModelConfig(model_name="mock/gpt-4"))
    
    # 循环
    loop: LoopConfig = field(default_factory=LoopConfig)
    
    # Bash
    bash: BashConfig = field(default_factory=BashConfig)
    
    # 缓存
    cache: OptimizedCacheConfig = field(default_factory=OptimizedCacheConfig)
    
    # 路由策略
    routing_strategy: RoutingStrategy = RoutingStrategy.BALANCED
    
    # 工具
    tools: list[str] = field(default_factory=lambda: ["bash", "read", "write", "edit"])
    
    @property
    def system_prompt(self) -> str:
        return """You are a helpful coding assistant.
You have access to tools. When you need to execute a command, respond with:
<tool_name>bash</tool_name>
<tool_input>{"command": "ls -la"}</tool_input>

Available tools: bash, read, write, edit
"""


# ============================================================================
# Harness Agent
# ============================================================================

class HarnessAgent:
    """
    端到端 Harness Agent (Phase 3 + Phase 4)
    
    集成:
    - Model: API 调用
    - Executor: 命令执行
    - Loop: 主循环控制
    - Cache: 请求缓存
    - Monitor: 资源监测 (Phase 4)
    - Router: 智能路由 (Phase 4)
    """
    
    def __init__(self, config: HarnessConfig | None = None, model=None):
        self.config = config or HarnessConfig()
        
        # 初始化组件
        # 如果提供了 model 实例，直接使用；否则根据配置创建
        if model is not None:
            self.model = model
        elif "mock" in self.config.model.model_name.lower():
            # Mock model for testing
            from core.model import MockModel
            self.model = MockModel(self.config.model)
        else:
            # Real LiteLLM model
            self.model = LitellmModel(self.config.model)
        
        self.executor = BashExecutor(self.config.bash)
        self.cache = OptimizedCache(self.config.cache)
        
        # Phase 4: 资源监测器 + 路由器
        self.monitor = get_monitor()
        router_config = None  # 使用默认配置
        self.router = get_router(router_config)
        
        # 消息历史
        self.messages: list[dict] = []
        
        # 循环统计
        self.loop_stats = LoopStats()
        
        # 工具注册
        self._tools: dict[str, callable] = {
            "bash": self._tool_bash,
            "read": self._tool_read,
            "write": self._tool_write,
            "edit": self._tool_edit,
        }
        
        logger.info(f"HarnessAgent initialized: model={self.config.model.model_name}, "
                   f"router={self.config.routing_strategy.value}")
    
    # =========================================================================
    # 工具
    # =========================================================================
    
    def _tool_bash(self, tool_input: dict) -> str:
        """Bash 工具"""
        command = tool_input.get("command", "")
        result = self.executor.execute(command)
        
        output = f"<returncode>{result.returncode}</returncode>\n<output>\n{result.stdout}\n</output>"
        if result.stderr:
            output += f"\n<stderr>\n{result.stderr}\n</stderr>"
        if result.truncated:
            output += "\n<warning>Output was truncated</warning>"
        
        return output
    
    def _tool_read(self, tool_input: dict) -> str:
        """读取文件"""
        path = tool_input.get("path", "")
        try:
            with open(path, "r") as f:
                content = f.read()
            return f"<output>\n{content}\n</output>"
        except Exception as e:
            return f"<error>{e}</error>"
    
    def _tool_write(self, tool_input: dict) -> str:
        """写入文件"""
        path = tool_input.get("path", "")
        content = tool_input.get("content", "")
        try:
            with open(path, "w") as f:
                f.write(content)
            return f"<output>Written {len(content)} bytes to {path}</output>"
        except Exception as e:
            return f"<error>{e}</error>"
    
    def _tool_edit(self, tool_input: dict) -> str:
        """编辑文件"""
        path = tool_input.get("path", "")
        old_text = tool_input.get("old", "")
        new_text = tool_input.get("new", "")
        try:
            with open(path, "r") as f:
                content = f.read()
            if old_text not in content:
                return f"<error>Pattern not found in {path}</error>"
            content = content.replace(old_text, new_text)
            with open(path, "w") as f:
                f.write(content)
            return f"<output>Edited {path}</output>"
        except Exception as e:
            return f"<error>{e}</error>"
    
    # =========================================================================
    # 工具解析
    # =========================================================================
    
    def _parse_tool_call(self, text: str) -> tuple[str, dict] | None:
        """
        解析工具调用
        
        格式:
        <tool_name>bash</tool_name>
        <tool_input>{"command": "ls"}</tool_input>
        
        Returns:
            (tool_name, tool_input) or None
        """
        import re
        
        tool_match = re.search(r'<tool_name>(\w+)</tool_name>', text)
        input_match = re.search(r'<tool_input>(.*?)</tool_input>', text, re.DOTALL)
        
        if not tool_match:
            return None
        
        tool_name = tool_match.group(1)
        
        if not input_match:
            return tool_name, {}
        
        # 解析 JSON
        import json
        try:
            tool_input = json.loads(input_match.group(1))
            return tool_name, tool_input
        except json.JSONDecodeError:
            return tool_name, {}
    
    def _execute_tools(self, actions: list[dict]) -> list[dict]:
        """执行工具调用"""
        observations = []
        
        for action in actions:
            tool_name = action.get("tool", "")
            tool_input = action.get("input", {})
            
            if tool_name not in self._tools:
                obs = {
                    "role": "tool",
                    "content": f"<error>Unknown tool: {tool_name}</error>",
                    "tool": tool_name,
                }
                observations.append(obs)
                continue
            
            try:
                result = self._tools[tool_name](tool_input)
                obs = {
                    "role": "tool",
                    "content": result,
                    "tool": tool_name,
                }
            except Exception as e:
                obs = {
                    "role": "tool",
                    "content": f"<error>{e}</error>",
                    "tool": tool_name,
                }
            
            observations.append(obs)
        
        return observations
    
    # =========================================================================
    # 主循环
    # =========================================================================
    
    def run(self, user_message: str, max_turns: int | None = None) -> dict:
        """
        运行 Agent 处理用户查询
        
        Args:
            user_message: 用户消息
            max_turns: 最大轮数
            
        Returns:
            {
                "content": str,          # 最终回复
                "loop_stats": dict,      # 循环统计
                "cost_stats": dict,      # 成本统计
                "cache_stats": dict,     # 缓存统计
            }
        """
        # 重置状态
        system_prompt = self.config.system_prompt
        self.messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]
        self.loop_stats = LoopStats()
        
        config = self.config.loop
        if max_turns is not None:
            config = LoopConfig(max_steps=max_turns)
        
        final_response = ""
        exit_status = "MAX_STEPS"
        
        try:
            while True:
                # 检查步骤限制
                if config.max_steps > 0 and self.loop_stats.steps >= config.max_steps:
                    raise StepLimitExceeded(config.max_steps)
                
                # 检查成本限制
                if config.max_cost > 0 and self.loop_stats.cost >= config.max_cost:
                    raise CostLimitExceeded(config.max_cost, self.loop_stats.cost)
                
                # Phase 4: 路由决策 (每轮根据系统状态)
                task = Task(
                    type=TaskType.AGENTIC,
                    estimated_tokens=sum(len(m.get("content", "")) for m in self.messages) // 4,
                )
                routing_decision = self.router.route(task)
                
                # 查询模型
                logger.debug(f"Step {self.loop_stats.steps + 1}: Querying model...")
                step_start = time.time()
                response = self.model.query(self.messages)
                step_latency = (time.time() - step_start) * 1000
                
                # Phase 4: 记录到监测器
                step_cost = response.get("extra", {}).get("cost", 0.0)
                tokens = response.get("extra", {}).get("usage", {}).get("total_tokens", 0)
                success = response.get("role") == "assistant"
                self.monitor.record_model_call(
                    latency_ms=step_latency,
                    success=success,
                    tokens=tokens,
                    model_name=self.config.model.model_name,
                )
                self.loop_stats.record_step(step_cost)
                
                # 提取回复内容
                content = response.get("content", "")
                
                # 检查退出指令
                if content.strip().lower() in ["exit", "done", "complete", "finished"]:
                    exit_status = "COMPLETED"
                    final_response = response
                    break
                
                # 解析工具调用
                tool_call = self._parse_tool_call(content)
                
                if tool_call:
                    tool_name, tool_input = tool_call
                    
                    # 添加助手回复
                    self.messages.append({
                        "role": "assistant",
                        "content": content,
                    })
                    
                    # 执行工具
                    logger.debug(f"Executing tool: {tool_name}")
                    observations = self._execute_tools([{"tool": tool_name, "input": tool_input}])
                    
                    # 添加观察结果
                    for obs in observations:
                        self.messages.append(obs)
                else:
                    # 没有工具调用，可能是最终回复
                    if self.loop_stats.steps >= config.max_steps - 1:
                        final_response = content
                        break
                    
                    # 继续循环
                    self.messages.append({
                        "role": "assistant",
                        "content": content,
                    })
                    # 添加一个提示
                    self.messages.append({
                        "role": "user",
                        "content": "Please use a tool to complete the task, or say 'done' if finished.",
                    })
                
        except LoopInterrupt as e:
            logger.info(f"Loop interrupted: {e}")
            exit_status = e.exit_status
            final_response = getattr(e, 'submission', '') or ""
        
        except Exception as e:
            logger.error(f"Loop error: {e}")
            exit_status = "ERROR"
            self.loop_stats.error = str(e)
        
        return {
            "content": final_response,
            "exit_status": exit_status,
            "loop_stats": self.loop_stats.to_dict(),
            "cost_stats": self.model.get_stats(),
            "cache_stats": self.cache.get_stats(),
            "system_status": self.get_system_status(),
            "messages": self.messages,
        }
    
    # =========================================================================
    # 兼容方法
    # =========================================================================
    # 系统状态 (Phase 4)
    # =========================================================================
    
    def get_system_status(self) -> dict:
        """获取系统状态 (供外部调用)"""
        status = self.monitor.get_status()
        return {
            "health_score": status.health_score,
            "is_healthy": status.is_healthy,
            "cpu_percent": status.cpu_percent,
            "memory_percent": status.memory_percent,
            "avg_latency_ms": status.avg_latency_ms,
            "success_rate": status.success_rate,
            "cache_hit_rate": status.cache_hit_rate,
            "tokens_per_minute": status.tokens_per_minute,
            "cost_today": status.cost_today,
            "recommended_action": status.recommended_action,
        }
    
    # =========================================================================
    
    def query(self, user_message: str, **kwargs) -> dict:
        """query() 是 run() 的别名"""
        return self.run(user_message, **kwargs)
    
    def reset(self):
        """重置 Agent 状态"""
        self.messages = []
        self.loop_stats = LoopStats()
        if hasattr(self.model, 'reset_stats'):
            self.model.reset_stats()
        elif hasattr(self.model, 'reset'):
            self.model.reset()
        self.cache.clear()


# ============================================================================
# 便捷函数
# ============================================================================

_default_agent: HarnessAgent | None = None


def get_agent(config: HarnessConfig | None = None) -> HarnessAgent:
    """获取默认 Agent"""
    global _default_agent
    if _default_agent is None:
        _default_agent = HarnessAgent(config)
    return _default_agent


def query(user_message: str, **kwargs) -> dict:
    """快捷查询函数"""
    return get_agent().query(user_message, **kwargs)
