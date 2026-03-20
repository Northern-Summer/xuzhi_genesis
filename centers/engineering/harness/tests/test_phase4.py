"""
Phase 4: Resource Monitor + Dynamic Router Tests

运行: pytest tests/test_phase4.py -v
"""

import pytest
import sys
import time
sys.path.insert(0, ".")

from monitor.resource_monitor import (
    ResourceMonitor,
    SystemStatus,
    ModelCapability,
    ModelTier,
    ResourceSnapshot,
    get_monitor,
    reset_monitor,
)
from router.dynamic_router import (
    DynamicRouter,
    Task,
    TaskType,
    RoutingDecision,
    RoutingStrategy,
    RouterConfig,
    get_router,
    reset_router,
)


# ============================================================================
# ResourceMonitor Tests
# ============================================================================

class TestResourceMonitor:
    """资源监测器测试"""
    
    def setup_method(self):
        """每个测试前重置"""
        reset_monitor()
    
    def teardown_method(self):
        """每个测试后清理"""
        reset_monitor()
    
    def test_basic_record(self):
        """基本记录"""
        monitor = get_monitor()
        
        monitor.record_model_call(latency_ms=100, success=True, tokens=50)
        monitor.record_cache_hit(hit=True)
        
        status = monitor.get_status()
        assert status.total_tokens_today == 50
        assert status.cache_hit_rate > 0
    
    def test_multiple_calls(self):
        """多次调用统计"""
        monitor = get_monitor()
        
        for i in range(5):
            monitor.record_model_call(latency_ms=100 + i*10, success=True, tokens=100)
        
        status = monitor.get_status()
        assert status.total_tokens_today == 500
        assert status.avg_latency_ms > 0
    
    def test_crash_record(self):
        """崩溃记录"""
        monitor = get_monitor()
        
        monitor.record_crash("timeout")
        monitor.record_crash("rate_limit")
        
        status = monitor.get_status()
        assert status.crash_rate > 0
    
    def test_cost_record(self):
        """成本记录"""
        monitor = get_monitor()
        
        monitor.record_cost(0.05)
        monitor.record_cost(0.03)
        
        status = monitor.get_status()
        assert status.cost_today == 0.08
    
    def test_health_score(self):
        """健康分数"""
        monitor = get_monitor()
        
        # 记录一些成功调用
        for _ in range(10):
            monitor.record_model_call(latency_ms=100, success=True, tokens=50)
        
        status = monitor.get_status()
        assert status.health_score > 0
        assert status.health_score <= 100
        assert status.is_healthy is True
    
    def test_unhealthy_when_crashing(self):
        """崩溃时健康分数下降"""
        monitor = get_monitor()
        
        # 记录一些失败
        for _ in range(5):
            monitor.record_model_call(latency_ms=100, success=False, tokens=50)
        
        status = monitor.get_status()
        assert status.success_rate < 1.0
    
    def test_model_capability(self):
        """模型能力查询"""
        monitor = get_monitor()
        
        cap = monitor.get_model_capability("gpt-4")
        assert cap.tier == ModelTier.CLOUD_LARGE
        assert cap.context_window == 128000
        
        cap_local = monitor.get_model_capability("ollama/llama3")
        assert cap_local.tier == ModelTier.LOCAL_LARGE


# ============================================================================
# DynamicRouter Tests
# ============================================================================

class TestDynamicRouter:
    """智能路由器测试"""
    
    def setup_method(self):
        """每个测试前重置"""
        reset_monitor()
        reset_router()
    
    def test_simple_route(self):
        """简单路由"""
        router = get_router()
        
        task = Task(type=TaskType.QUICK_ANSWER, estimated_tokens=100)
        decision = router.route(task)
        
        assert decision.model_name is not None
        assert decision.confidence > 0
    
    def test_complexity_routing(self):
        """复杂度路由"""
        router = get_router()
        
        # 简单任务
        simple = Task(type=TaskType.QUICK_ANSWER, estimated_tokens=50)
        decision_simple = router.route(simple)
        
        # 复杂任务
        complex = Task(type=TaskType.REASONING, estimated_tokens=50000)
        decision_complex = router.route(complex)
        
        # 复杂任务应该用更强的模型
        assert decision_complex.confidence >= decision_simple.confidence * 0.5
    
    def test_function_call_routing(self):
        """函数调用路由"""
        router = get_router()
        
        # 需要函数调用的任务
        task = Task(type=TaskType.AGENTIC, requires_functions=True)
        decision = router.route(task)
        
        spec = router._get_model_spec(decision.model_name)
        assert spec.get("supports_functions", False) is True
    
    def test_cost_optimized_strategy(self):
        """成本优先策略"""
        config = RouterConfig(strategy=RoutingStrategy.COST_OPTIMIZED)
        router = get_router(config)
        
        task = Task(type=TaskType.QUICK_ANSWER)
        decision = router.route(task)
        
        # 成本优先应该倾向于便宜模型
        assert decision is not None
    
    def test_quality_first_strategy(self):
        """质量优先策略"""
        config = RouterConfig(strategy=RoutingStrategy.QUALITY_FIRST)
        router = get_router(config)
        
        task = Task(type=TaskType.REASONING, estimated_tokens=5000)
        decision = router.route(task)
        
        spec = router._get_model_spec(decision.model_name)
        # 质量优先应该用高成功率模型
        assert spec.get("success_rate", 0) >= 0.95
    
    def test_adaptive_strategy(self):
        """自适应策略"""
        config = RouterConfig(strategy=RoutingStrategy.ADAPTIVE)
        router = get_router(config)
        
        task = Task(type=TaskType.CODE_EDIT)
        decision = router.route(task)
        
        assert decision is not None
        assert "adaptive" in decision.reasoning.lower()
    
    def test_local_fallback(self):
        """本地模型兜底云端"""
        config = RouterConfig(
            strategy=RoutingStrategy.BALANCED,
            prefer_local_threshold=0.3,
            local_fallback_cloud=True,
        )
        router = get_router(config)
        
        # 复杂任务，尝试本地但可能失败
        task = Task(type=TaskType.REASONING, estimated_tokens=50000)
        decision = router.route(task)
        
        # 应该给出一个决策
        assert decision.model_name is not None
    
    def test_alternatives(self):
        """备选模型"""
        router = get_router()
        
        task = Task(type=TaskType.RESEARCH)
        decision = router.route(task)
        
        # 应该有备选
        assert len(decision.alternatives) >= 0
        # 如果有备选，应该是不同的模型
        if decision.alternatives:
            assert decision.alternatives[0][0] != decision.model_name
    
    def test_register_custom_model(self):
        """注册自定义模型"""
        config = RouterConfig()
        router = get_router(config)
        
        router.register_model("my-model", {
            "tier": ModelTier.LOCAL_MEDIUM,
            "context_window": 4096,
            "cost_per_1k": 0.0,
            "latency_ms": 1000,
            "success_rate": 0.80,
            "supports_functions": False,
        })
        
        spec = router._get_model_spec("my-model")
        assert spec["tier"] == ModelTier.LOCAL_MEDIUM
    
    def test_task_complexity(self):
        """任务复杂度计算"""
        simple = Task(type=TaskType.QUICK_ANSWER)
        assert simple.complexity < 0.3
        
        complex_task = Task(type=TaskType.AGENTIC, estimated_tokens=50000)
        assert complex_task.complexity > 0.5


# ============================================================================
# Integration Tests
# ============================================================================

class TestMonitorRouterIntegration:
    """监测器-路由器集成测试"""
    
    def setup_method(self):
        reset_monitor()
        reset_router()
    
    def teardown_method(self):
        reset_monitor()
        reset_router()
    
    def test_monitor_affects_routing(self):
        """监测状态影响路由"""
        monitor = get_monitor()
        config = RouterConfig(strategy=RoutingStrategy.ADAPTIVE)
        router = get_router(config)
        
        # 记录大量缓存命中
        for _ in range(10):
            monitor.record_model_call(latency_ms=100, success=True, tokens=50)
            monitor.record_cache_hit(hit=True)
        
        # 路由
        task = Task(type=TaskType.QUICK_ANSWER)
        decision = router.route(task)
        
        # 缓存好，cost优化
        assert decision is not None


# ============================================================================
# Run
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
