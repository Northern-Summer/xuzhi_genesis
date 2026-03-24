"""
Phase 3: 端到端集成测试

运行: pytest tests/test_phase3.py -v
"""

import pytest
import sys
sys.path.insert(0, ".")

from harness.harness import HarnessAgent, HarnessConfig, get_agent
from core.model import MockModel, ModelConfig
from executor.bash import BashExecutor, BashConfig


# ============================================================================
# 配置
# ============================================================================

def make_test_config():
    return HarnessConfig(
        model=ModelConfig(model_name="mock/gpt-4"),
    )


# ============================================================================
# Agent 初始化测试
# ============================================================================

class TestHarnessAgentInit:
    """Agent 初始化测试"""
    
    def test_default_init(self):
        """默认初始化"""
        agent = HarnessAgent()
        assert agent.model is not None
        assert agent.executor is not None
        assert agent.cache is not None
        assert agent.loop_stats.steps == 0
    
    def test_custom_config(self):
        """自定义配置"""
        config = make_test_config()
        agent = HarnessAgent(config)
        assert agent.config.model.model_name == "mock/gpt-4"
    
    def test_mock_model(self):
        """Mock 模型"""
        config = make_test_config()
        agent = HarnessAgent(config)
        assert isinstance(agent.model, MockModel)


# ============================================================================
# Bash 执行器测试
# ============================================================================

class TestBashExecutor:
    """Bash 执行器测试"""
    
    def test_simple_command(self):
        """简单命令"""
        executor = BashExecutor()
        result = executor.execute("echo hello")
        assert result.success
        assert "hello" in result.stdout
    
    def test_returncode(self):
        """返回码"""
        executor = BashExecutor()
        result = executor.execute("exit 0")
        assert result.returncode == 0
        
        result = executor.execute("exit 1")
        assert result.returncode == 1
    
    def test_dangerous_blocked(self):
        """危险命令被阻止"""
        executor = BashExecutor()
        result = executor.execute("rm -rf /")
        assert not result.success
        assert "blocked" in result.stderr.lower()


# ============================================================================
# 工具解析测试
# ============================================================================

class TestToolParsing:
    """工具解析测试"""
    
    def test_parse_bash_tool(self):
        """解析 Bash 工具"""
        config = make_test_config()
        agent = HarnessAgent(config)
        
        text = '<tool_name>bash</tool_name>\n<tool_input>{"command": "ls -la"}</tool_input>'
        tool_name, tool_input = agent._parse_tool_call(text)
        
        assert tool_name == "bash"
        assert tool_input == {"command": "ls -la"}
    
    def test_parse_edit_tool(self):
        """解析 Edit 工具"""
        config = make_test_config()
        agent = HarnessAgent(config)
        
        text = '<tool_name>edit</tool_name>\n<tool_input>{"path": "test.py", "old": "foo", "new": "bar"}</tool_input>'
        tool_name, tool_input = agent._parse_tool_call(text)
        
        assert tool_name == "edit"
        assert tool_input["path"] == "test.py"
    
    def test_no_tool(self):
        """无工具调用"""
        config = make_test_config()
        agent = HarnessAgent(config)
        
        text = "Hello, how can I help you?"
        result = agent._parse_tool_call(text)
        assert result is None


# ============================================================================
# 工具执行测试
# ============================================================================

class TestToolExecution:
    """工具执行测试"""
    
    def test_execute_bash(self):
        """执行 Bash 工具"""
        config = make_test_config()
        agent = HarnessAgent(config)
        
        result = agent._tool_bash({"command": "echo test"})
        assert "<returncode>0</returncode>" in result
        assert "test" in result
    
    def test_execute_read(self, tmp_path):
        """执行 Read 工具"""
        config = make_test_config()
        agent = HarnessAgent(config)
        
        # 创建临时文件
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello World")
        
        result = agent._tool_read({"path": str(test_file)})
        assert "Hello World" in result
    
    def test_execute_write(self, tmp_path):
        """执行 Write 工具"""
        config = make_test_config()
        agent = HarnessAgent(config)
        
        test_file = tmp_path / "output.txt"
        result = agent._tool_write({"path": str(test_file), "content": "Test content"})
        
        assert test_file.read_text() == "Test content"
    
    def test_execute_edit(self, tmp_path):
        """执行 Edit 工具"""
        config = make_test_config()
        agent = HarnessAgent(config)
        
        test_file = tmp_path / "edit.txt"
        test_file.write_text("Hello foo world")
        
        result = agent._tool_edit({"path": str(test_file), "old": "foo", "new": "bar"})
        
        assert test_file.read_text() == "Hello bar world"


# ============================================================================
# 主循环测试
# ============================================================================

class TestMainLoop:
    """主循环测试"""
    
    def test_simple_conversation(self):
        """简单对话"""
        config = make_test_config()
        agent = HarnessAgent(config)
        
        agent.model.set_responses([
            {"role": "assistant", "content": "Hello!", "extra": {"actions": [], "cost": 0.001}},
        ])
        
        result = agent.run("Hi", max_turns=2)
        assert result["exit_status"] in ["MAX_STEPS", "COMPLETED"]
        assert result["loop_stats"]["steps"] >= 1
    
    def test_with_tool_call(self):
        """带工具调用"""
        config = make_test_config()
        agent = HarnessAgent(config)
        
        agent.model.set_responses([
            {"role": "assistant", "content": '<tool_name>bash</tool_name>\n<tool_input>{"command": "echo hello"}</tool_input>', "extra": {"actions": [{"tool": "bash"}], "cost": 0.001}},
            {"role": "assistant", "content": "Done!", "extra": {"actions": [], "cost": 0.001}},
        ])
        
        result = agent.run("Run echo", max_turns=5)
        assert result["exit_status"] == "MAX_STEPS"
        assert result["loop_stats"]["steps"] >= 2
    
    def test_step_limit(self):
        """步骤限制"""
        config = make_test_config()
        agent = HarnessAgent(config)
        
        agent.model.set_responses([
            {"role": "assistant", "content": "step", "extra": {"actions": [], "cost": 0.001}},
        ] * 10)
        
        result = agent.run("Count steps", max_turns=3)
        assert result["loop_stats"]["steps"] <= 3
    
    def test_reset(self):
        """重置"""
        config = make_test_config()
        agent = HarnessAgent(config)
        
        agent.model.set_responses([
            {"role": "assistant", "content": "Hi", "extra": {"actions": [], "cost": 0.001}},
        ])
        
        result = agent.run("Hello", max_turns=2)
        assert agent.loop_stats.steps >= 0
        
        agent.reset()
        assert agent.loop_stats.steps == 0
        assert len(agent.messages) == 0


# ============================================================================
# 统计测试
# ============================================================================

class TestStats:
    """统计测试"""
    
    def test_cost_tracking(self):
        """成本追踪"""
        config = make_test_config()
        agent = HarnessAgent(config)
        
        agent.model.set_responses([
            {"role": "assistant", "content": "Hi", "extra": {"actions": [], "cost": 0.005}},
        ])
        
        result = agent.run("Hello", max_turns=2)
        assert result["cost_stats"]["total_cost"] == "$0.005000"
    
    def test_cache_stats(self):
        """缓存统计"""
        config = make_test_config()
        agent = HarnessAgent(config)
        
        result = agent.run("Hello", max_turns=1)
        assert "cache_stats" in result
        assert "total_requests" in result["cache_stats"]


# ============================================================================
# 便捷函数测试
# ============================================================================

class TestConvenienceFunctions:
    """便捷函数测试"""
    
    def test_query_shortcut(self):
        """query 快捷方式"""
        from harness.harness import query
        
        result = query("test", max_turns=1)
        assert "content" in result
    
    def test_get_agent_singleton(self):
        """单例"""
        agent1 = get_agent()
        agent2 = get_agent()
        assert agent1 is agent2


# ============================================================================
# 运行
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
