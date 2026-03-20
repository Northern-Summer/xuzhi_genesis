"""
自维持Agent核心 - Self-Sustaining Agent Core

设计原则:
1. 发现优于假设 - 不预设模型列表
2. 韧性优于正确 - 任何组件都可能失败
3. 降级优于崩溃 - 多层降级策略
4. 沉默优于唠叨 - 减少无意义的tokens

30天无人值守的目标:
- 自动发现可用资源
- 自动绕过故障组件
- 自动从错误中恢复
- 最小化人类干预
"""

from __future__ import annotations

import time
import subprocess
import json
import threading
from dataclasses import dataclass, field
from typing import Callable, Any
from enum import Enum
from collections import deque
import logging

logger = logging.getLogger("sustaining")


# ============================================================================
# 发现层 - Discover what's actually available
# ============================================================================

class ModelSource(Enum):
    OLLAMA = "ollama"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    UNKNOWN = "unknown"


@dataclass
class DiscoveredModel:
    """实际发现的模型"""
    name: str           # ollama list 中的原始名称
    source: ModelSource
    size_mb: float = 0.0
    modified: str = ""
    
    # 探测得到的能力 (运行时)
    probed: bool = False
    supports_functions: bool = False
    supports_vision: bool = False
    avg_latency_ms: float = 0.0
    success_rate: float = 0.0
    is_healthy: bool = True
    
    # 故障追踪
    consecutive_failures: int = 0
    total_calls: int = 0
    total_failures: int = 0
    
    @property
    def effective_name(self) -> str:
        """用于API调用的名称"""
        if self.source == ModelSource.OLLAMA:
            return f"ollama/{self.name}"
        return self.name
    
    @property
    def health_score(self) -> float:
        """健康分数"""
        if self.total_calls == 0:
            return 1.0
        score = self.success_rate - (self.consecutive_failures * 0.2)
        return max(0.0, min(1.0, score))


class ModelDiscovery:
    """
    模型发现 - 运行时探测而非预设
    
    不再问"有什么模型？"然后假设
    而是实际探测每个模型的真实能力
    """
    
    def __init__(self):
        self._discovered: list[DiscoveredModel] = []
        self._probe_lock = threading.Lock()
        self._last_probe: float = 0
        self._probe_interval: float = 300  # 5分钟不要重复探测
        
        with self._probe_lock:
            self._discovered = []
            
            # 1. 发现 Ollama 模型
            self._discover_ollama()
            
            # 2. TODO: 发现云端模型 (需要配置)
            # self._discover_cloud()
            
            now = time.time()
            self._last_probe = now
        
        logger.info(f"Discovered {len(self._discovered)} models")
        for m in self._discovered:
            logger.debug(f"  - {m.name} ({m.source.value})")
        
    def _discover_ollama(self) -> None:
        """运行 ollama list 获取真实列表"""
        try:
            result = subprocess.run(
                ["ollama", "list"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                import re as _re
                for line in result.stdout.strip().split("\n")[1:]:  # skip header
                    parts = [p for p in _re.split(r'\s{2,}', line) if p]
                    if len(parts) >= 4:
                        name, sid, size_str = parts[0], parts[1], parts[2]
                        modified = ' '.join(parts[3:])
                        size_mb = 0.0
                        if size_str == "-":
                            pass
                        elif size_str.endswith("GB"):
                            size_mb = float(size_str[:-2]) * 1024
                        elif size_str.endswith("MB"):
                            size_mb = float(size_str[:-2])
                        self._discovered.append(DiscoveredModel(
                            name=name,
                            source=ModelSource.OLLAMA,
                            size_mb=size_mb,
                            modified=modified,
                        ))
            else:
                logger.warning(f"ollama list failed: {result.stderr}")
        except FileNotFoundError:
            logger.warning("ollama not found")
        except subprocess.TimeoutExpired:
            logger.error("ollama list timed out")
    
    def probe_model(self, model: DiscoveredModel, timeout: float = 30) -> dict:
        """
        探测模型真实能力
        
        发送一个简单请求，看它是否能响应
        不假设 - 实际测试
        """
        if model.probed:
            return {
                "supports_functions": model.supports_functions,
                "supports_vision": model.supports_vision,
                "avg_latency_ms": model.avg_latency_ms,
            }
        
        # 简单探测: 发送一个短问句
        probe_prompt = "Reply with exactly one word: ok"
        
        start = time.time()
        success = False
        error_msg = ""
        
        try:
            if model.source == ModelSource.OLLAMA:
                result = subprocess.run(
                    ["ollama", "run", model.name, probe_prompt],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )
                success = result.returncode == 0 and len(result.stdout.strip()) > 0
                error_msg = result.stderr[:200] if result.stderr else ""
        except subprocess.TimeoutExpired:
            error_msg = "timeout"
        except Exception as e:
            error_msg = str(e)[:100]
        
        latency = (time.time() - start) * 1000
        
        with self._probe_lock:
            model.probed = True
            model.avg_latency_ms = latency
            if success:
                model.success_rate = 1.0
            # 注意: supports_functions/vision 需要更复杂的探测
            # 暂时基于名称启发式
            model.supports_functions = "function" in model.name.lower() or "tool" in model.name.lower()
            model.supports_vision = "vl" in model.name.lower() or "vision" in model.name.lower()
        
        return {
            "success": success,
            "latency_ms": latency,
            "error": error_msg,
        }
    

    def discover_all(self, force: bool = False) -> list[DiscoveredModel]:
        """发现所有模型，可选强制刷新
        
        Args:
            force: True = 跳过缓存重新探测
        """
        with self._probe_lock:
            if not force:
                now = time.time()
                if (now - self._last_probe) < self._probe_interval:
                    return self._discovered
            
            # 重新探测
            self._discovered = []
            self._discover_ollama()
            self._last_probe = time.time()
        
        return self._discovered
    def get_healthy_models(self) -> list[DiscoveredModel]:
        """获取当前健康的模型列表"""
        all_models = self.discover_all()
        return [m for m in all_models if m.health_score > 0.3]


# ============================================================================
# 健康追踪 - Circuit Breaker + Exponential Backoff
# ============================================================================

@dataclass
class CircuitState:
    """熔断器状态 - 使用类常量避免Enum比较问题"""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """
    熔断器 - 防止故障级联
    
    状态机:
    CLOSED (正常) → 失败超过阈值 → OPEN (熔断)
    OPEN → 冷却时间到 → HALF_OPEN (试探)
    HALF_OPEN → 成功 → CLOSED
    HALF_OPEN → 失败 → OPEN
    """
    
    def __init__(
        self,
        name: str,
        failure_threshold: int = 3,
        recovery_timeout: float = 60.0,
        half_open_successes: int = 1,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_successes = half_open_successes
        
        self._state = "closed"
        self._consecutive_failures = 0
        self._consecutive_successes = 0
        self._last_failure_time = time.time()
        self._lock = threading.Lock()
    
    @property
    def state(self) -> CircuitState:
        with self._lock:
            if self._state == "open":
                # 检查是否超时
                if time.time() - self._last_failure_time >= self.recovery_timeout:
                    self._state = "half_open"
                    logger.info(f"CircuitBreaker {self.name}: OPEN → HALF_OPEN")
            return self._state
    
    def record_success(self) -> None:
        with self._lock:
            if self._state == "half_open":
                self._consecutive_successes += 1
                if self._consecutive_successes >= self.half_open_successes:
                    self._state = "closed"
                    self._consecutive_failures = 0
                    self._consecutive_successes = 0
                    logger.info(f"CircuitBreaker {self.name}: HALF_OPEN → CLOSED")
            elif self._state == "closed":
                self._consecutive_failures = 0
    
    def record_failure(self) -> None:
        with self._lock:
            self._consecutive_failures += 1
            self._last_failure_time = time.time()
            
            if self._state == "half_open":
                self._state = "open"
                self._consecutive_successes = 0
                logger.warning(f"CircuitBreaker {self.name}: HALF_OPEN → OPEN (failed)")
            elif self._state == "closed":
                if self._consecutive_failures >= self.failure_threshold:
                    self._state = "open"
                    logger.warning(f"CircuitBreaker {self.name}: CLOSED → OPEN (threshold: {self.failure_threshold})")
    
    def allow_request(self) -> bool:
        """是否允许请求通过"""
        return self.state != "open"


# ============================================================================
# 自维持执行器 - 真正的容错执行
# ============================================================================

@dataclass
class ExecutionResult:
    """执行结果"""
    success: bool
    output: str = ""
    error: str = ""
    model_used: str = ""
    latency_ms: float = 0.0
    from_cache: bool = False
    
    @property
    def was_successful(self) -> bool:
        return self.success


class SelfSustainingExecutor:
    """
    自维持执行器
    
    核心原则:
    1. 不假设任何模型可用
    2. 多层降级: 尝试多个模型，一个失败自动切换下一个
    3. 熔断保护: 连续失败自动隔离
    4. 缓存兜底: 重复请求直接返回
    """
    
    def __init__(self, cache_ttl: float = 300, max_retries: int = 2):
        self.discovery = ModelDiscovery()
        self.cache: dict[str, tuple[float, ExecutionResult]] = {}
        self.cache_ttl = cache_ttl
        self.max_retries = max_retries
        
        # 每个模型的熔断器
        self._breakers: dict[str, CircuitBreaker] = {}
        self._lock = threading.Lock()
        
        # 统计
        self._stats = {
            "total_requests": 0,
            "cache_hits": 0,
            "model_switches": 0,
            "circuit_breaks": 0,
        }
    
    def execute(self, prompt: str, require_functions: bool = False) -> ExecutionResult:
        """
        执行提示词，自动处理所有故障
        
        流程:
        1. 检查缓存
        2. 获取健康模型列表
        3. 尝试每个模型，直到成功
        4. 记录结果，更新健康状态
        """
        cache_key = self._make_cache_key(prompt)
        
        # 1. 缓存检查
        if cache_key in self.cache:
            cached_time, cached_result = self.cache[cache_key]
            if time.time() - cached_time < self.cache_ttl:
                self._stats["cache_hits"] += 1
                cached_result.from_cache = True
                logger.debug(f"Cache hit: {prompt[:50]}...")
                return cached_result
        
        self._stats["total_requests"] += 1
        
        # 2. 获取可用模型
        models = self.discovery.get_healthy_models()
        if not models:
            # 强制重新发现
            models = self.discovery.discover_all(force=True)
        
        if not models:
            return ExecutionResult(
                success=False,
                error="No models available",
            )
        
        # 3. 按健康分数排序
        models.sort(key=lambda m: m.health_score, reverse=True)
        
        # 4. 尝试每个模型
        last_error = ""
        for attempt in range(self.max_retries):
            for model in models:
                breaker = self._get_breaker(model.name)
                
                if not breaker.allow_request():
                    self._stats["circuit_breaks"] += 1
                    continue
                
                result = self._try_model(model, prompt, require_functions)
                last_error = result.error
                
                if result.success:
                    self._update_model_health(model, success=True)
                    breaker.record_success()
                    self._cache_result(cache_key, result)
                    return result
                else:
                    self._update_model_health(model, success=False)
                    breaker.record_failure()
                    self._stats["model_switches"] += 1
                    logger.warning(f"Model {model.name} failed: {result.error}")
        
        # 所有模型都失败了
        return ExecutionResult(
            success=False,
            error=f"All models failed. Last error: {last_error}",
        )
    
    def _try_model(
        self,
        model: DiscoveredModel,
        prompt: str,
        require_functions: bool,
        timeout: float = 60,
    ) -> ExecutionResult:
        """尝试调用单个模型"""
        start = time.time()
        
        try:
            if model.source == ModelSource.OLLAMA:
                result = subprocess.run(
                    ["ollama", "run", model.name, prompt],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )
                
                if result.returncode == 0:
                    output = self._strip_ansi(result.stdout)
                    return ExecutionResult(
                        success=True,
                        output=output.strip(),
                        model_used=model.name,
                        latency_ms=(time.time() - start) * 1000,
                    )
                else:
                    return ExecutionResult(
                        success=False,
                        error=result.stderr.strip()[:200],
                        model_used=model.name,
                    )
            else:
                return ExecutionResult(
                    success=False,
                    error=f"Unknown source: {model.source}",
                )
        except subprocess.TimeoutExpired:
            return ExecutionResult(
                success=False,
                error="timeout",
                model_used=model.name,
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                error=str(e)[:100],
                model_used=model.name,
            )
    
    def _update_model_health(self, model: DiscoveredModel, success: bool) -> None:
        """更新模型健康状态"""
        with self.discovery._probe_lock:
            model.total_calls += 1
            if success:
                model.total_failures = max(0, model.total_failures - 1)
                if model.consecutive_failures > 0:
                    model.consecutive_failures -= 1
            else:
                model.total_failures += 1
                model.consecutive_failures += 1
    
    def _get_breaker(self, model_name: str) -> CircuitBreaker:
        """获取熔断器"""
        with self._lock:
            if model_name not in self._breakers:
                self._breakers[model_name] = CircuitBreaker(
                    name=model_name,
                    failure_threshold=3,
                    recovery_timeout=60,
                )
            return self._breakers[model_name]
    
    def _make_cache_key(self, prompt: str) -> str:
        """缓存key = prompt的简单hash"""
        import hashlib
        return hashlib.md5(prompt.encode()).hexdigest()
    
    def _strip_ansi(self, text: str) -> str:
        """移除ANSI转义序列"""
        import re
        # ANSI escape sequences (including \x1b[?25h cursor sequences)
        ansi_escape = re.compile(
            r'\x1b\[[0-9;]*[a-zA-Z]'   # ESC[...X (standard)
            r'|\x1b\[[?][0-9;]*[a-zA-Z]'  # ESC[?##X (private)
            r'|\x1b\][^\x07]*\x07'       # ESC]...BEL
            r'|\x1b[^a-zA-Z]*[a-zA-Z]'  # ESC other
        )
        return ansi_escape.sub('', text)
    
    def _cache_result(self, key: str, result: ExecutionResult) -> None:
        """缓存结果"""
        # 限制缓存大小
        if len(self.cache) > 1000:
            # 删除最老的
            oldest = min(self.cache.items(), key=lambda x: x[1][0])
            del self.cache[oldest[0]]
        self.cache[key] = (time.time(), result)
    
    def get_stats(self) -> dict:
        """获取统计"""
        return {
            **self._stats,
            "cache_hit_rate": self._stats["cache_hits"] / max(1, self._stats["total_requests"]),
            "healthy_models": len(self.discovery.get_healthy_models()),
        }


# ============================================================================
# 全局实例
# ============================================================================

_global_executor: SelfSustainingExecutor | None = None


def get_executor() -> SelfSustainingExecutor:
    global _global_executor
    if _global_executor is None:
        _global_executor = SelfSustainingExecutor()
    return _global_executor
