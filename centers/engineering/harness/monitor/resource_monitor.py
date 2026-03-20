"""
资源监测器 - Phase 4 核心组件

功能:
- 实时监测系统资源状态
- 模型性能追踪 (延迟、成功率、崩溃率)
- Token消耗速率
- 缓存命中率
- 本地模型负载

设计原则:
- 非侵入式: 不影响主流程性能
- 增量更新: 移动平均，避免剧烈波动
- 多维度: 覆盖硬件/OS/应用层
"""

from __future__ import annotations

import time
import psutil
import threading
from dataclasses import dataclass, field
from typing import Optional
from collections import deque
from enum import Enum
import logging

logger = logging.getLogger("monitor")


# ============================================================================
# 数据结构
# ============================================================================

class ModelTier(Enum):
    """模型层级"""
    CLOUD_LARGE = "cloud_large"      # GPT-4, Claude-3, Gemini-Pro
    CLOUD_MEDIUM = "cloud_medium"    # GPT-3.5, Gemini-Flash
    CLOUD_SMALL = "cloud_small"      # 小型云模型
    LOCAL_LARGE = "local_large"      # 7B 量级
    LOCAL_MEDIUM = "local_medium"    # 3B 量级
    LOCAL_SMALL = "local_small"      # 1B 量级


@dataclass
class ModelCapability:
    """模型能力描述"""
    tier: ModelTier
    context_window: int          # 最大上下文 (tokens)
    avg_latency_ms: float        # 平均延迟
    cost_per_1k_tokens: float    # 云端成本
    success_rate: float          # 成功率 (0-1)
    max_retries: int             # 最大重试次数
    
    # 能力标志
    supports_functions: bool = True
    supports_vision: bool = False
    supports_long_context: bool = False
    
    @property
    def is_cloud(self) -> bool:
        return self.tier in {
            ModelTier.CLOUD_LARGE,
            ModelTier.CLOUD_MEDIUM,
            ModelTier.CLOUD_SMALL,
        }
    
    @property
    def is_local(self) -> bool:
        return not self.is_cloud


@dataclass
class ResourceSnapshot:
    """资源快照"""
    timestamp: float
    # 系统资源
    cpu_percent: float
    memory_percent: float
    memory_available_mb: float
    
    # 模型性能
    model_latency_ms: float | None
    model_success: bool | None
    token_count: int | None
    
    # 缓存
    cache_hit: bool | None
    
    @property
    def age_ms(self) -> float:
        return (time.time() - self.timestamp) * 1000


@dataclass 
class SystemStatus:
    """系统整体状态"""
    # 资源
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    memory_available_mb: float = 0.0
    
    # 模型性能 (移动平均)
    avg_latency_ms: float = 0.0
    success_rate: float = 1.0
    crash_rate: float = 0.0
    
    # Token 消耗
    tokens_per_minute: float = 0.0
    total_tokens_today: int = 0
    
    # 缓存
    cache_hit_rate: float = 0.0
    
    # 成本 (云端)
    cost_per_hour: float = 0.0
    cost_today: float = 0.0
    
    # 推荐操作
    recommended_action: str = "nominal"  # nominal, prefer_local, prefer_cloud, throttle
    
    @property
    def health_score(self) -> float:
        """综合健康分数 (0-100)"""
        score = 100.0
        
        # CPU 惩罚
        if self.cpu_percent > 80:
            score -= (self.cpu_percent - 80) * 2
        elif self.cpu_percent > 60:
            score -= (self.cpu_percent - 60) * 0.5
            
        # 内存惩罚
        if self.memory_percent > 85:
            score -= (self.memory_percent - 85) * 3
        elif self.memory_percent > 70:
            score -= (self.memory_percent - 70) * 0.5
            
        # 成功率惩罚
        if self.success_rate < 0.95:
            score -= (0.95 - self.success_rate) * 100
            
        # 崩溃惩罚
        score -= self.crash_rate * 50
        
        return max(0.0, min(100.0, score))
    
    @property
    def is_healthy(self) -> bool:
        return self.health_score >= 70


# ============================================================================
# 资源监测器
# ============================================================================

class ResourceMonitor:
    """
    资源监测器
    
    使用方法:
    ```python
    monitor = ResourceMonitor()
    
    # 记录事件
    monitor.record_model_call(latency_ms=150, success=True, tokens=500)
    monitor.record_cache_hit(hit=True)
    
    # 获取状态
    status = monitor.get_status()
    print(f"Health: {status.health_score}, Recommended: {status.recommended_action}")
    ```
    """
    
    # 配置
    HISTORY_SIZE = 100       # 历史记录数量
    LATENCY_WINDOW = 50      # 延迟平均窗口
    RATE_WINDOW_SECONDS = 60 # 速率计算窗口 (秒)
    
    def __init__(self):
        self._lock = threading.RLock()
        
        # 历史记录
        self._history: deque[ResourceSnapshot] = deque(maxlen=self.HISTORY_SIZE)
        
        # 统计计数
        self._total_model_calls = 0
        self._total_success = 0
        self._total_crashes = 0
        self._total_tokens = 0
        
        # 速率追踪
        self._token_timeline: deque[tuple[float, int]] = deque(maxlen=1000)  # (timestamp, tokens)
        self._call_timeline: deque[tuple[float, bool]] = deque(maxlen=1000)   # (timestamp, success)
        
        # 时间窗口
        self._start_time = time.time()
        self._today_start = self._start_time  # 简化：每天重置
        
        # 系统资源采样 (后台线程)
        self._sampling_thread: threading.Thread | None = None
        self._stop_sampling = threading.Event()
        self._latest_system: dict = {
            "cpu_percent": 0.0,
            "memory_percent": 0.0,
            "memory_available_mb": 0.0,
        }
        
        self._start_sampling()
    
    # =========================================================================
    # 公开 API
    # =========================================================================
    
    def record_model_call(
        self,
        latency_ms: float,
        success: bool,
        tokens: int,
        model_name: str = "default",
    ) -> None:
        """记录一次模型调用"""
        with self._lock:
            snapshot = ResourceSnapshot(
                timestamp=time.time(),
                cpu_percent=self._latest_system["cpu_percent"],
                memory_percent=self._latest_system["memory_percent"],
                memory_available_mb=self._latest_system["memory_available_mb"],
                model_latency_ms=latency_ms,
                model_success=success,
                token_count=tokens,
                cache_hit=None,
            )
            self._history.append(snapshot)
            
            # 更新统计
            self._total_model_calls += 1
            if success:
                self._total_success += 1
            self._total_tokens += tokens
            
            # 更新速率时间线
            self._call_timeline.append((time.time(), success))
            self._token_timeline.append((time.time(), tokens))
    
    def record_cache_hit(self, hit: bool) -> None:
        """记录缓存命中"""
        with self._lock:
            # 找到最近的快照更新
            if self._history:
                last = self._history[-1]
                # 创建新的快照更新 cache_hit
                snapshot = ResourceSnapshot(
                    timestamp=last.timestamp,
                    cpu_percent=last.cpu_percent,
                    memory_percent=last.memory_percent,
                    memory_available_mb=last.memory_available_mb,
                    model_latency_ms=last.model_latency_ms,
                    model_success=last.model_success,
                    token_count=last.token_count,
                    cache_hit=hit,
                )
                self._history[-1] = snapshot
    
    def record_crash(self, error_type: str = "unknown") -> None:
        """记录一次崩溃"""
        with self._lock:
            self._total_crashes += 1
    
    def record_cost(self, cost_usd: float) -> None:
        """记录成本"""
        with self._lock:
            self._cost_today = getattr(self, '_cost_today', 0.0) + cost_usd
    
    def get_status(self) -> SystemStatus:
        """获取系统整体状态"""
        with self._lock:
            now = time.time()
            window_start = now - self.RATE_WINDOW_SECONDS
            
            # 过滤时间窗口内的记录
            recent_calls = [(t, s) for t, s in self._call_timeline if t >= window_start]
            recent_tokens = [(t, n) for t, n in self._token_timeline if t >= window_start]
            
            # 计算速率
            if recent_calls:
                successful = sum(1 for _, s in recent_calls if s)
                current_success_rate = successful / len(recent_calls)
                calls_per_minute = len(recent_calls) / (self.RATE_WINDOW_SECONDS / 60)
            else:
                current_success_rate = 1.0
                calls_per_minute = 0.0
            
            if recent_tokens:
                total_recent = sum(n for _, n in recent_tokens)
                tokens_per_minute = total_recent / (self.RATE_WINDOW_SECONDS / 60)
            else:
                tokens_per_minute = 0.0
            
            # 计算平均延迟 (最近 LATENCY_WINDOW 次)
            recent_latencies = [
                s.model_latency_ms for s in self._history
                if s.model_latency_ms is not None
            ][-self.LATENCY_WINDOW:]
            avg_latency = sum(recent_latencies) / len(recent_latencies) if recent_latencies else 0.0
            
            # 计算缓存命中率
            cache_hits = sum(1 for s in self._history if s.cache_hit is True)
            cache_misses = sum(1 for s in self._history if s.cache_hit is False)
            total_cache = cache_hits + cache_misses
            cache_hit_rate = cache_hits / total_cache if total_cache > 0 else 0.0
            
            # 崩溃率 (最近 100 次调用)
            recent_crashes = min(self._total_crashes, 10)  # 简化
            crash_rate = recent_crashes / max(self._total_model_calls, 1)
            
            # 推荐操作
            action = self._compute_recommended_action(
                cpu=self._latest_system["cpu_percent"],
                memory=self._latest_system["memory_percent"],
                success_rate=current_success_rate,
                avg_latency=avg_latency,
                cache_hit_rate=cache_hit_rate,
            )
            
            return SystemStatus(
                cpu_percent=self._latest_system["cpu_percent"],
                memory_percent=self._latest_system["memory_percent"],
                memory_available_mb=self._latest_system["memory_available_mb"],
                avg_latency_ms=avg_latency,
                success_rate=current_success_rate,
                crash_rate=crash_rate,
                tokens_per_minute=tokens_per_minute,
                total_tokens_today=self._total_tokens,
                cache_hit_rate=cache_hit_rate,
                cost_per_hour=getattr(self, '_cost_per_hour', 0.0),
                cost_today=getattr(self, '_cost_today', 0.0),
                recommended_action=action,
            )
    
    def get_model_capability(self, model_name: str) -> ModelCapability:
        """获取模型能力描述"""
        # 根据模型名称返回能力描述
        # 实际应用中应该从配置读取
        if "gpt-4" in model_name.lower() or "claude-3" in model_name.lower():
            tier = ModelTier.CLOUD_LARGE
            context = 128000
            cost = 0.01
        elif "gpt-3.5" in model_name.lower() or "gemini-flash" in model_name.lower():
            tier = ModelTier.CLOUD_MEDIUM
            context = 16385
            cost = 0.002
        elif "ollama" in model_name.lower() or "llama" in model_name.lower():
            tier = ModelTier.LOCAL_LARGE
            context = 4096
            cost = 0.0
        else:
            tier = ModelTier.CLOUD_SMALL
            context = 8192
            cost = 0.001
        
        return ModelCapability(
            tier=tier,
            context_window=context,
            avg_latency_ms=self._get_avg_latency_for_tier(tier),
            cost_per_1k_tokens=cost,
            success_rate=self._get_success_rate_for_tier(tier),
            max_retries=3 if tier in {ModelTier.CLOUD_LARGE, ModelTier.CLOUD_MEDIUM, ModelTier.CLOUD_SMALL} else 1,
        )
    
    def get_recent_history(self, n: int = 10) -> list[ResourceSnapshot]:
        """获取最近 n 条记录"""
        with self._lock:
            return list(self._history)[-n:]
    
    def reset_daily(self) -> None:
        """每日重置"""
        with self._lock:
            self._total_tokens = 0
            self._total_model_calls = 0
            self._total_success = 0
            self._total_crashes = 0
            self._cost_today = 0.0
            self._today_start = time.time()
            logger.info("Daily stats reset")
    
    # =========================================================================
    # 内部方法
    # =========================================================================
    
    def _start_sampling(self) -> None:
        """启动后台采样"""
        if self._sampling_thread is not None:
            return
        
        def _sample():
            while not self._stop_sampling.wait(timeout=5.0):  # 每5秒采样
                try:
                    self._latest_system = {
                        "cpu_percent": psutil.cpu_percent(interval=0.1),
                        "memory_percent": psutil.virtual_memory().percent,
                        "memory_available_mb": psutil.virtual_memory().available / (1024*1024),
                    }
                except Exception as e:
                    logger.warning(f"Sampling error: {e}")
        
        self._sampling_thread = threading.Thread(target=_sample, daemon=True)
        self._sampling_thread.start()
    
    def _compute_recommended_action(
        self,
        cpu: float,
        memory: float,
        success_rate: float,
        avg_latency: float,
        cache_hit_rate: float,
    ) -> str:
        """计算推荐操作"""
        # 资源紧张
        if cpu > 90 or memory > 90:
            return "throttle"
        
        # 成功率低
        if success_rate < 0.8:
            return "prefer_local"  # 切到本地减少云端调用

        # 延迟高但缓存好
        if avg_latency > 2000 and cache_hit_rate > 0.7:
            return "nominal"  # 缓存正在工作
        
        # 成本高企
        if cache_hit_rate < 0.5:
            return "prefer_local"  # 减少云端调用
        
        # 正常
        return "nominal"
    
    def _get_avg_latency_for_tier(self, tier: ModelTier) -> float:
        """获取层级平均延迟"""
        latencies = {
            ModelTier.CLOUD_LARGE: 1500,
            ModelTier.CLOUD_MEDIUM: 800,
            ModelTier.CLOUD_SMALL: 500,
            ModelTier.LOCAL_LARGE: 2000,
            ModelTier.LOCAL_MEDIUM: 1500,
            ModelTier.LOCAL_SMALL: 5000,
        }
        return latencies.get(tier, 1000)
    
    def _get_success_rate_for_tier(self, tier: ModelTier) -> float:
        """获取层级成功率"""
        rates = {
            ModelTier.CLOUD_LARGE: 0.98,
            ModelTier.CLOUD_MEDIUM: 0.95,
            ModelTier.CLOUD_SMALL: 0.90,
            ModelTier.LOCAL_LARGE: 0.85,
            ModelTier.LOCAL_MEDIUM: 0.75,
            ModelTier.LOCAL_SMALL: 0.60,
        }
        return rates.get(tier, 0.80)
    
    def __del__(self):
        """清理"""
        self._stop_sampling.set()
        if self._sampling_thread:
            self._sampling_thread.join(timeout=1.0)


# ============================================================================
# 全局实例
# ============================================================================

_global_monitor: ResourceMonitor | None = None


def get_monitor() -> ResourceMonitor:
    """获取全局监测器"""
    global _global_monitor
    if _global_monitor is None:
        _global_monitor = ResourceMonitor()
    return _global_monitor


def reset_monitor() -> None:
    """重置全局监测器"""
    global _global_monitor
    if _global_monitor:
        _global_monitor._stop_sampling.set()
        if _global_monitor._sampling_thread:
            _global_monitor._sampling_thread.join(timeout=1.0)
    _global_monitor = None
