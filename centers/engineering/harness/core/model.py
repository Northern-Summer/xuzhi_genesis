"""
模型抽象层 - Phase 2
参考: mini-SWE-agent LitellmModel

核心设计:
- 统一接口: Model.query(messages) -> dict
- 请求缓存: 相同 messages → 缓存结果
- 重试机制: tenacity 自动重试
- 成本追踪: 记录每次请求 cost
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Literal

import tenacity
from pydantic import BaseModel, Field

logger = logging.getLogger("model")


# ============================================================================
# 配置模型
# ============================================================================

class ModelConfig(BaseModel):
    """模型配置基类"""
    model_name: str = Field(description="模型名称，含 provider 前缀")
    timeout: int = Field(default=60, description="请求超时(秒)")
    max_retries: int = Field(default=3, description="最大重试次数")
    retry_delay: float = Field(default=1.0, description="初始重试延迟(秒)")
    cache_enabled: bool = Field(default=True, description="启用请求缓存")


@dataclass
class CostStats:
    """成本统计"""
    total_cost: float = 0.0
    total_requests: int = 0
    cache_hits: int = 0
    
    def record(self, cost: float, cached: bool = False):
        self.total_cost += cost
        self.total_requests += 1
        if cached:
            self.cache_hits += 1


# ============================================================================
# 请求缓存
# ============================================================================

class RequestCache:
    """
    请求缓存 - 减少重复 API 调用
    
    缓存策略:
    - Key: messages 的 JSON 序列化 + model_name 的 hash
    - TTL: 5 分钟 (300秒)
    - 淘汰: LRU (内存中)
    """
    
    def __init__(self, ttl: int = 300, max_entries: int = 1000):
        self.ttl = ttl
        self.max_entries = max_entries
        self._cache: dict[str, tuple[float, dict]] = {}
        self._access_order: list[str] = []
        self.hits = 0
        self.misses = 0
        self.sets = 0
    
    def _make_key(self, messages: list[dict], model_name: str) -> str:
        """生成缓存 key"""
        # 只序列化 content，忽略其他元数据
        content_hash = hashlib.sha256(
            json.dumps([m.get("content", "") for m in messages], sort_keys=True).encode()
        ).hexdigest()[:16]
        return f"{model_name}:{content_hash}"
    
    def get(self, messages: list[dict], model_name: str) -> dict | None:
        """获取缓存结果"""
        key = self._make_key(messages, model_name)
        
        if key not in self._cache:
            self.misses += 1
            return None
        
        timestamp, cached_data = self._cache[key]
        
        # 检查 TTL
        if time.time() - timestamp > self.ttl:
            del self._cache[key]
            self._access_order.remove(key)
            self.misses += 1
            return None
        
        # LRU: 移动到末尾
        self._access_order.remove(key)
        self._access_order.append(key)
        
        self.hits += 1
        logger.debug(f"Cache HIT: {key[:20]}...")
        return cached_data
    
    def set(self, messages: list[dict], data: dict, model_name: str = ""):
        """设置缓存"""
        key = self._make_key(messages, model_name)
        
        # LRU 淘汰
        while len(self._cache) >= self.max_entries and self._access_order:
            oldest_key = self._access_order.pop(0)
            del self._cache[oldest_key]
        
        self._cache[key] = (time.time(), data)
        self._access_order.append(key)
        self.sets += 1
        logger.debug(f"Cache SET: {key[:20]}...")
    
    def get_stats(self) -> dict:
        """获取缓存统计"""
        total = self.hits + self.misses
        return {
            "entries": len(self._cache),
            "max_entries": self.max_entries,
            "ttl": self.ttl,
            "hits": self.hits,
            "misses": self.misses,
            "sets": self.sets,
            "hit_rate": f"{self.hits / total * 100:.1f}%" if total else "N/A",
        }
    
    def clear(self):
        """清空缓存"""
        self._cache.clear()
        self._access_order.clear()


# ============================================================================
# 模型基类
# ============================================================================

class Model(ABC):
    """
    模型抽象基类
    
    设计参考:
    - mini-SWE-agent LitellmModel
    - InterruptAgentFlow 异常体系
    """
    
    def __init__(self, config: ModelConfig):
        self.config = config
        self.cache = RequestCache() if config.cache_enabled else None
        self.cost_stats = CostStats()
        self._logger = logging.getLogger(f"model.{self.__class__.__name__}")
    
    @abstractmethod
    def _query_impl(self, messages: list[dict]) -> dict:
        """
        实际查询实现
        
        返回格式:
        {
            "role": "assistant",
            "content": "...",
            "extra": {
                "actions": [...],  # 工具调用
                "cost": 0.001,
                "usage": {...}
            }
        }
        """
        pass
    
    def query(self, messages: list[dict]) -> dict:
        """
        查询模型，支持缓存和重试
        
        优化点:
        1. 缓存命中 → 直接返回，不消耗 API
        2. 失败 → tenacity 自动重试
        3. 超时 → 抛出异常，交由上层处理
        """
        # 检查缓存
        if self.cache:
            cached = self.cache.get(messages, self.config.model_name)
            if cached:
                self.cost_stats.record(0, cached=True)
                return cached
        
        # 执行查询
        try:
            response = self._query_with_retry(messages)
        except Exception as e:
            self._logger.error(f"Query failed after retries: {e}")
            raise
        
        # 更新缓存
        if self.cache:
            self.cache.set(messages, response, self.config.model_name)
        
        # 记录成本
        cost = response.get("extra", {}).get("cost", 0.0)
        self.cost_stats.record(cost)
        
        return response
    
    def _query_with_retry(self, messages: list[dict]) -> dict:
        """带重试的查询"""
        
        @tenacity.retry(
            stop=tenacity.stop_after_attempt(self.config.max_retries),
            wait=tenacity.wait_exponential(
                multiplier=self.config.retry_delay,
                min=self.config.retry_delay,
                max=30
            ),
            reraise=True,
            before_sleep=lambda retry_state: self._logger.warning(
                f"Retry {retry_state.attempt_number}/{self.config.max_retries} "
                f"after error: {retry_state.outcome.exception()}"
            )
        )
        def _call():
            return self._query_impl(messages)
        
        return _call()
    
    @abstractmethod
    def format_message(self, **kwargs) -> dict:
        """格式化消息"""
        pass
    
    @abstractmethod
    def format_observation(self, output: dict, **kwargs) -> dict:
        """格式化观察结果"""
        pass
    
    def get_stats(self) -> dict:
        """获取统计信息"""
        total = self.cost_stats.total_requests
        hits = self.cost_stats.cache_hits
        return {
            "total_requests": total,
            "cache_hits": hits,
            "cache_hit_rate": f"{hits/total*100:.1f}%" if total else "N/A",
            "total_cost": f"${self.cost_stats.total_cost:.6f}",
        }


# ============================================================================
# 异常体系 (参考 InterruptAgentFlow)
# ============================================================================

class ModelInterrupt(Exception):
    """模型相关中断基类"""
    pass


class QueryTimeout(ModelInterrupt):
    """查询超时"""
    pass


class ModelUnavailable(ModelInterrupt):
    """模型不可用"""
    pass


class RateLimitExceeded(ModelInterrupt):
    """速率限制"""
    pass


# ============================================================================
# LiteLLM 实现
# ============================================================================

import os


class LitellmModel(Model):
    """
    LiteLLM 模型实现
    
    支持:
    - OpenAI, Anthropic, Google, 本地模型等
    - 请求缓存
    - 成本追踪
    """
    
    def __init__(self, config: ModelConfig | None = None):
        super().__init__(config or ModelConfig())
        
        # LiteLLM 配置
        self._setup_litellm()
    
    def _setup_litellm(self):
        """配置 LiteLLM"""
        # Lazy import
        global litellm
        import litellm
        
        # 设置 API key (从环境变量或配置)
        if self.config.api_key:
            os.environ[self.config.model_provider.upper() + "_API_KEY"] = self.config.api_key
        
        # 禁用详细日志 (除非在 debug 模式)
        if not self._logger.isEnabledFor(logging.DEBUG):
            litellm.suppress_debug_messages = True
    
    def _query_impl(self, messages: list[dict]) -> dict:
        """
        实际查询 LiteLLM
        
        Returns:
            {
                "role": "assistant", 
                "content": "...",
                "extra": {"actions": [], "cost": 0.001}
            }
        """
        try:
            response = litellm.completion(
                model=self.config.model_name,
                messages=messages,
                api_key=self.config.api_key,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
            )
            
            # 提取响应
            choice = response["choices"][0]
            message = choice["message"]
            
            # 提取 usage
            usage = response.get("usage", {})
            
            # 估算成本 (LiteLLM 会自动估算)
            cost = litellm.completion_cost(response) if hasattr(litellm, 'completion_cost') else 0.001
            
            # 解析动作 (从 content 中提取工具调用)
            actions = self._parse_actions(message.get("content", ""))
            
            return {
                "role": message.get("role", "assistant"),
                "content": message.get("content", ""),
                "extra": {
                    "actions": actions,
                    "cost": cost,
                    "usage": {
                        "prompt_tokens": usage.get("prompt_tokens", 0),
                        "completion_tokens": usage.get("completion_tokens", 0),
                        "total_tokens": usage.get("total_tokens", 0),
                    }
                }
            }
            
        except litellm.RateLimitError as e:
            raise RateLimitExceeded(str(e)) from e
        except litellm.Timeout as e:
            raise QueryTimeout(str(e)) from e
        except Exception as e:
            self._logger.error(f"LiteLLM error: {e}")
            raise
    
    def _parse_actions(self, content: str) -> list[dict]:
        """
        解析内容中的工具调用
        
        格式:
        <tool_name>bash</tool_name>
        <tool_input>{"command": "ls"}</tool_input>
        
        Returns:
            [{"tool": "bash", "input": {"command": "ls"}}]
        """
        import re
        import json
        
        actions = []
        
        # 匹配 <tool_name>...</tool_name><tool_input>...</tool_input>
        pattern = r'<tool_name>(\w+)</tool_name>\s*<tool_input>(.*?)</tool_input>'
        
        for match in re.finditer(pattern, content, re.DOTALL):
            tool_name = match.group(1)
            try:
                tool_input = json.loads(match.group(2))
            except json.JSONDecodeError:
                tool_input = {"raw": match.group(2).strip()}
            
            actions.append({
                "tool": tool_name,
                "input": tool_input,
            })
        
        return actions
    
    def format_message(self, role: str, content: str, **kwargs) -> dict:
        """格式化消息"""
        return {"role": role, "content": content, **kwargs}
    
    def format_observation(self, output: dict, **kwargs) -> dict:
        """格式化观察结果"""
        return {
            "role": "tool",
            "content": output.get("content", str(output)),
            **kwargs
        }


# ============================================================================
# Mock Model (测试用)
# ============================================================================

class MockModel(Model):
    """
    Mock 模型 - 用于测试，不调用真实 API
    """
    
    def __init__(self, config: ModelConfig | None = None, responses: list[dict] | None = None):
        super().__init__(config or ModelConfig())
        self._responses = responses or [
            {
                "role": "assistant",
                "content": "I'll help you with that.",
                "extra": {"actions": [], "cost": 0.001}
            }
        ]
        self._response_index = 0
    
    def _query_impl(self, messages: list[dict]) -> dict:
        """返回预设响应"""
        if self._response_index < len(self._responses):
            response = self._responses[self._response_index]
            self._response_index += 1
            return response
        
        # 默认响应
        return {
            "role": "assistant",
            "content": "Done.",
            "extra": {"actions": [], "cost": 0.001}
        }
    
    def format_message(self, role: str, content: str, **kwargs) -> dict:
        return {"role": role, "content": content, **kwargs}
    
    def format_observation(self, output: dict, **kwargs) -> dict:
        return {"role": "tool", "content": output.get("content", str(output)), **kwargs}
    
    def set_responses(self, responses: list[dict]):
        """设置预设响应"""
        self._responses = responses
        self._response_index = 0
    
    def reset(self):
        """重置"""
        self._response_index = 0
