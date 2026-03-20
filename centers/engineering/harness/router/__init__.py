"""
Dynamic Router Module - Phase 4

Components:
- DynamicRouter: 智能路由决策
- Task: 任务描述
- RoutingDecision: 路由决策结果
- RoutingStrategy: 路由策略枚举
"""

from .dynamic_router import (
    DynamicRouter,
    Task,
    TaskType,
    RoutingDecision,
    RoutingStrategy,
    RouterConfig,
    get_router,
    reset_router,
)

__all__ = [
    "DynamicRouter",
    "Task",
    "TaskType",
    "RoutingDecision",
    "RoutingStrategy",
    "RouterConfig",
    "get_router",
    "reset_router",
]
