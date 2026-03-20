"""
智能路由器 - Phase 4 核心组件

功能:
- 任务复杂度评估
- 模型能力匹配
- 成本-质量权衡
- 动态路由决策

设计原则:
- 基于 ResourceMonitor 的实时状态
- 可配置策略
- 适配器模式支持新模型
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable
from enum import Enum
import logging

from monitor.resource_monitor import (
    ResourceMonitor, 
    SystemStatus, 
    ModelCapability,
    ModelTier,
    get_monitor,
)

logger = logging.getLogger("router")


# ============================================================================
# 任务类型与复杂度
# ============================================================================

class TaskType(Enum):
    """任务类型"""
    QUICK_ANSWER = "quick_answer"        # 简单问答
    CODE_COMPLETION = "code_completion"  # 代码补全
    CODE_EDIT = "code_edit"              # 代码编辑
    REASONING = "reasoning"             # 复杂推理
    CREATIVE = "creative"               # 创意写作
    RESEARCH = "research"               # 研究分析
    AGENTIC = "agentic"                # 代理任务 (多步骤)


@dataclass
class Task:
    """任务描述"""
    type: TaskType
    estimated_tokens: int = 0           # 预估输入 tokens
    expected_output_tokens: int = 0    # 预估输出 tokens
    requires_functions: bool = False   # 需要函数调用
    requires_vision: bool = False      # 需要视觉
    priority: int = 1                  # 优先级 (1-5, 5最高)
    deadline_ms: float | None = None   # 截止时间
    
    @property
    def complexity(self) -> float:
        """复杂度评分 (0-1)"""
        score = 0.0
        
        # 基于类型
        type_scores = {
            TaskType.QUICK_ANSWER: 0.1,
            TaskType.CODE_COMPLETION: 0.3,
            TaskType.CODE_EDIT: 0.4,
            TaskType.REASONING: 0.6,
            TaskType.CREATIVE: 0.5,
            TaskType.RESEARCH: 0.7,
            TaskType.AGENTIC: 0.9,
        }
        score += type_scores.get(self.type, 0.3)
        
        # 基于 tokens
        if self.estimated_tokens > 50000:
            score += 0.2
        elif self.estimated_tokens > 10000:
            score += 0.1
        
        # 基于功能需求
        if self.requires_functions:
            score += 0.1
        
        return min(1.0, score)
    
    @property
    def is_urgent(self) -> bool:
        """是否紧急"""
        if self.deadline_ms is None:
            return False
        return True


@dataclass
class RoutingDecision:
    """路由决策"""
    model_name: str                     # 选择的模型
    reasoning: str                      # 决策理由
    confidence: float                   # 置信度 (0-1)
    alternatives: list[tuple[str, float]] = field(default_factory=list)  # (model, score)
    
    @property
    def use_cache(self) -> bool:
        """是否使用缓存"""
        return self.confidence > 0.9


# ============================================================================
# 路由策略
# ============================================================================

class RoutingStrategy(Enum):
    """路由策略"""
    COST_OPTIMIZED = "cost_optimized"     # 成本优先
    QUALITY_FIRST = "quality_first"        # 质量优先
    BALANCED = "balanced"                 # 平衡
    LATENCY_FIRST = "latency_first"       # 延迟优先
    ADAPTIVE = "adaptive"                 # 自适应 (根据系统状态)


@dataclass
class RouterConfig:
    """路由器配置"""
    strategy: RoutingStrategy = RoutingStrategy.BALANCED
    
    # 成本阈值
    max_cost_per_request: float = 0.10    # 最大单次成本
    max_hourly_cost: float = 5.0          # 最大小时成本
    
    # 延迟阈值
    max_latency_ms: float = 10000         # 最大延迟
    
    # 本地模型配置
    prefer_local_threshold: float = 0.4    # 复杂度低于此用本地
    local_fallback_cloud: bool = True     # 本地失败时自动切云端
    
    # 可用模型
    available_models: list[str] = field(default_factory=list)
    
    # 自适应参数
    cache_weight: float = 0.2             # 缓存命中率权重
    latency_weight: float = 0.3           # 延迟权重
    cost_weight: float = 0.2             # 成本权重
    quality_weight: float = 0.3           # 质量权重


# ============================================================================
# 智能路由器
# ============================================================================

class DynamicRouter:
    """
    智能路由器
    
    使用方法:
    ```python
    router = DynamicRouter(config)
    
    task = Task(type=TaskType.CODE_EDIT, estimated_tokens=500)
    decision = router.route(task)
    
    print(f"Use {decision.model_name}: {decision.reasoning}")
    ```
    """
    
    # 模型注册表
    MODEL_REGISTRY: dict[str, dict] = {
        # 云端模型
        "gpt-4": {
            "tier": ModelTier.CLOUD_LARGE,
            "context_window": 128000,
            "cost_per_1k": 0.03,
            "latency_ms": 1500,
            "success_rate": 0.98,
            "supports_functions": True,
            "supports_vision": True,
        },
        "gpt-3.5-turbo": {
            "tier": ModelTier.CLOUD_MEDIUM,
            "context_window": 16385,
            "cost_per_1k": 0.002,
            "latency_ms": 800,
            "success_rate": 0.95,
            "supports_functions": True,
            "supports_vision": False,
        },
        "claude-3-opus": {
            "tier": ModelTier.CLOUD_LARGE,
            "context_window": 200000,
            "cost_per_1k": 0.015,
            "latency_ms": 1800,
            "success_rate": 0.99,
            "supports_functions": True,
            "supports_vision": True,
        },
        "claude-3-haiku": {
            "tier": ModelTier.CLOUD_MEDIUM,
            "context_window": 200000,
            "cost_per_1k": 0.00025,
            "latency_ms": 500,
            "success_rate": 0.95,
            "supports_functions": True,
            "supports_vision": False,
        },
        "gemini-pro": {
            "tier": ModelTier.CLOUD_LARGE,
            "context_window": 128000,
            "cost_per_1k": 0.00125,
            "latency_ms": 1200,
            "success_rate": 0.97,
            "supports_functions": True,
            "supports_vision": True,
        },
        # 本地模型 (Ollama)
        "llama3": {
            "tier": ModelTier.LOCAL_LARGE,
            "context_window": 8192,
            "cost_per_1k": 0.0,
            "latency_ms": 2000,
            "success_rate": 0.85,
            "supports_functions": False,
            "supports_vision": False,
        },
        "codellama": {
            "tier": ModelTier.LOCAL_LARGE,
            "context_window": 16384,
            "cost_per_1k": 0.0,
            "latency_ms": 2500,
            "success_rate": 0.80,
            "supports_functions": False,
            "supports_vision": False,
        },
        "phi-3": {
            "tier": ModelTier.LOCAL_MEDIUM,
            "context_window": 4096,
            "cost_per_1k": 0.0,
            "latency_ms": 1500,
            "success_rate": 0.75,
            "supports_functions": False,
            "supports_vision": False,
        },
        "qwen2.5": {
            "tier": ModelTier.LOCAL_LARGE,
            "context_window": 32768,
            "cost_per_1k": 0.0,
            "latency_ms": 3000,
            "success_rate": 0.82,
            "supports_functions": False,
            "supports_vision": False,
        },
    }
    
    def __init__(
        self,
        config: RouterConfig | None = None,
        monitor: ResourceMonitor | None = None,
    ):
        self.config = config or RouterConfig()
        self.monitor = monitor or get_monitor()
        
        # 注册自定义模型
        self._custom_models: dict[str, dict] = {}
    
    def register_model(self, name: str, specs: dict) -> None:
        """注册自定义模型"""
        self._custom_models[name] = specs
        logger.info(f"Registered model: {name}")
    
    def route(self, task: Task) -> RoutingDecision:
        """
        为任务选择最佳模型
        
        Args:
            task: 任务描述
            
        Returns:
            RoutingDecision: 包含模型选择和理由
        """
        start = time.time()
        
        # 获取系统状态
        status = self.monitor.get_status()
        
        # 获取候选模型
        candidates = self._get_candidate_models(task)
        
        # 计算得分
        scored = []
        for model_name in candidates:
            model_spec = self._get_model_spec(model_name)
            score = self._compute_score(task, model_spec, status)
            scored.append((model_name, score))
        
        # 排序
        scored.sort(key=lambda x: x[1], reverse=True)
        
        if not scored:
            # 兜底
            return RoutingDecision(
                model_name="gpt-3.5-turbo",
                reasoning="No suitable model found, using default",
                confidence=0.1,
            )
        
        best_model, best_score = scored[0]
        
        # 构建决策
        alternatives = scored[1:4]  # 前3个备选
        
        decision = RoutingDecision(
            model_name=best_model,
            reasoning=self._build_reasoning(task, best_model, status),
            confidence=min(1.0, best_score),
            alternatives=alternatives,
        )
        
        logger.debug(f"Routed '{task.type.value}' to {best_model} "
                    f"(confidence={decision.confidence:.2f}, took {time.time()-start:.3f}s)")
        
        return decision
    
    def route_multiple(self, tasks: list[Task]) -> list[RoutingDecision]:
        """批量路由"""
        return [self.route(t) for t in tasks]
    
    # =========================================================================
    # 内部方法
    # =========================================================================
    

    def _is_local_tier(self, tier) -> bool:
        """检查是否本地模型"""
        return tier in {ModelTier.LOCAL_LARGE, ModelTier.LOCAL_MEDIUM, ModelTier.LOCAL_SMALL}

    def _get_model_spec(self, model_name: str) -> dict:
        """获取模型规格"""
        # 优先查注册表
        if model_name in self.MODEL_REGISTRY:
            return self.MODEL_REGISTRY[model_name]
        if model_name in self._custom_models:
            return self._custom_models[model_name]
        
        # 未知模型，尝试解析
        return {
            "tier": ModelTier.CLOUD_MEDIUM,
            "context_window": 16385,
            "cost_per_1k": 0.001,
            "latency_ms": 1000,
            "success_rate": 0.90,
            "supports_functions": True,
            "supports_vision": False,
        }
    
    def _get_candidate_models(self, task: Task) -> list[str]:
        """获取候选模型列表"""
        all_models = set(self.MODEL_REGISTRY.keys()) | set(self._custom_models.keys())
        
        # 如果配置了可用模型，过滤
        if self.config.available_models:
            all_models &= set(self.config.available_models)
        
        candidates = []
        
        for model in all_models:
            spec = self._get_model_spec(model)
            
            # 检查上下文限制
            if task.estimated_tokens > spec.get("context_window", 0):
                continue
            
            # 检查功能需求
            if task.requires_functions and not spec.get("supports_functions", False):
                continue
            if task.requires_vision and not spec.get("supports_vision", False):
                continue
            
            candidates.append(model)
        
        # 兜底
        if not candidates:
            candidates = ["gpt-3.5-turbo"]
        
        return candidates
    
    def _compute_score(self, task: Task, model_spec: dict, status: SystemStatus) -> float:
        """计算模型-任务匹配度"""
        strategy = self.config.strategy
        
        if strategy == RoutingStrategy.COST_OPTIMIZED:
            return self._score_cost_optimized(task, model_spec, status)
        elif strategy == RoutingStrategy.QUALITY_FIRST:
            return self._score_quality_first(task, model_spec, status)
        elif strategy == RoutingStrategy.LATENCY_FIRST:
            return self._score_latency_first(task, model_spec, status)
        elif strategy == RoutingStrategy.ADAPTIVE:
            return self._score_adaptive(task, model_spec, status)
        else:  # BALANCED
            return self._score_balanced(task, model_spec, status)
    
    def _score_cost_optimized(self, task: Task, spec: dict, status: SystemStatus) -> float:
        """成本优先评分"""
        score = 0.0
        
        # 成本得分 (越低越好)
        cost = spec.get("cost_per_1k", 0.0)
        cost_score = 1.0 - min(1.0, cost / 0.03)  # 归一化，最大$0.03
        score += cost_score * 0.5
        
        # 缓存命中率 (高好)
        score += status.cache_hit_rate * 0.3
        
        # 成功率 (高好)
        score += spec.get("success_rate", 0.9) * 0.2
        
        return score
    
    def _score_quality_first(self, task: Task, spec: dict, status: SystemStatus) -> float:
        """质量优先评分"""
        score = 0.0
        
        # 成功率 (最重要)
        score += spec.get("success_rate", 0.9) * 0.4
        
        # 延迟 (低好)
        latency = spec.get("latency_ms", 1000)
        latency_score = 1.0 - min(1.0, latency / 3000)
        score += latency_score * 0.3
        
        # 上下文窗口 (大大好)
        ctx = spec.get("context_window", 16385)
        ctx_score = min(1.0, ctx / 128000)
        score += ctx_score * 0.2
        
        # 成本 (低好)
        cost = spec.get("cost_per_1k", 0.0)
        cost_score = 1.0 - min(1.0, cost / 0.03)
        score += cost_score * 0.1
        
        return score
    
    def _score_latency_first(self, task: Task, spec: dict, status: SystemStatus) -> float:
        """延迟优先评分"""
        score = 0.0
        
        # 延迟 (最重要)
        latency = spec.get("latency_ms", 1000)
        latency_score = 1.0 - min(1.0, latency / 3000)
        score += latency_score * 0.6
        
        # 成功率
        score += spec.get("success_rate", 0.9) * 0.3
        
        # 成本
        score += (1.0 - min(1.0, spec.get("cost_per_1k", 0.0) / 0.03)) * 0.1
        
        return score
    
    def _score_adaptive(self, task: Task, spec: dict, status: SystemStatus) -> float:
        """自适应评分 - 根据系统状态动态调整"""
        score = 0.0
        
        # 系统负载调整
        if status.recommended_action == "throttle":
            # 系统紧张，优先考虑本地和缓存
            if spec.get("cost_per_1k", 0.0) == 0:  # 本地
                score += 0.4
            score += status.cache_hit_rate * 0.4
        elif status.recommended_action == "prefer_local":
            # 鼓励使用本地
            if self._is_local_tier(spec.get("tier", ModelTier.CLOUD_MEDIUM)):
                score += 0.3
        else:
            # 正常状态，平衡评分
            score += self._score_balanced(task, spec, status) * 0.7
            return score
        
        # 任务复杂度调整
        if task.complexity < self.config.prefer_local_threshold:
            # 简单任务，鼓励本地
            if self._is_local_tier(spec.get("tier", ModelTier.CLOUD_MEDIUM)):
                score += 0.3
        
        # 成功率
        score += spec.get("success_rate", 0.9) * 0.2
        
        return score
    
    def _score_balanced(self, task: Task, spec: dict, status: SystemStatus) -> float:
        """平衡评分"""
        score = 0.0
        
        # 延迟 (30%)
        latency = spec.get("latency_ms", 1000)
        latency_score = 1.0 - min(1.0, latency / 3000)
        score += latency_score * 0.30
        
        # 成功率 (30%)
        score += spec.get("success_rate", 0.9) * 0.30
        
        # 成本 (20%)
        cost = spec.get("cost_per_1k", 0.0)
        cost_score = 1.0 - min(1.0, cost / 0.03)
        score += cost_score * 0.20
        
        # 缓存命中率 (20%)
        score += status.cache_hit_rate * 0.20
        
        return score
    
    def _build_reasoning(self, task: Task, model_name: str, status: SystemStatus) -> str:
        """构建决策理由"""
        spec = self._get_model_spec(model_name)
        parts = []
        
        parts.append(f"Selected {model_name}")
        
        if self._is_local_tier(spec.get("tier", ModelTier.CLOUD_MEDIUM)):
            parts.append("(local)")
        else:
            cost = spec.get("cost_per_1k", 0)
            parts.append(f"(${cost:.4f}/1k)")
        
        # 根据策略添加原因
        if self.config.strategy == RoutingStrategy.COST_OPTIMIZED:
            parts.append("cost-optimized")
        elif self.config.strategy == RoutingStrategy.QUALITY_FIRST:
            parts.append("quality-first")
        elif self.config.strategy == RoutingStrategy.ADAPTIVE:
            parts.append(f"adaptive ({status.recommended_action})")
        
        # 系统状态提示
        if status.cache_hit_rate < 0.5:
            parts.append("low cache")
        if status.avg_latency_ms > 2000:
            parts.append("high latency")
        
        return " ".join(parts)


# ============================================================================
# 全局实例
# ============================================================================

_global_router: DynamicRouter | None = None


def get_router(config: RouterConfig | None = None) -> DynamicRouter:
    """获取全局路由器"""
    global _global_router
    if _global_router is None or config is not None:
        _global_router = DynamicRouter(config)
    return _global_router


def reset_router() -> None:
    """重置全局路由器"""
    global _global_router
    _global_router = None
