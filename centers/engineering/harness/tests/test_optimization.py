"""
优化测试 - Phase 优化
测试: 压缩、缓存效率提升

运行: pytest tests/test_optimization.py -v
"""

import pytest
import sys
import os
# 正确设置路径：从 tests/ 到 harness 根目录
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from context.compression import (
    CompressionConfig,
    compress_thought_tags,
    compress_bash_output,
    compress_observation,
    compress_messages,
    estimate_tokens,
    compute_compression_stats,
)
from context.optimized_cache import (
    OptimizedCacheConfig,
    OptimizedCache,
)


# ============================================================================
# 压缩测试
# ============================================================================

class TestThoughtCompression:
    """Thought 标签压缩测试"""
    
    def test_compress_thought(self):
        """压缩长 thought"""
        config = CompressionConfig(compress_thought=True)
        text = "<thought>我需要先查看目录结构，然后读取文件内容，理解代码逻辑，最后进行修改</thought>"
        
        result = compress_thought_tags(text, config)
        
        assert "<think>" in result
        assert len(result) < len(text)
    
    def test_remove_thought(self):
        """删除 thought (激进模式)"""
        config = CompressionConfig(remove_thought=True)
        text = "<thought>我需要先查看目录结构</thought>然后执行命令"
        
        result = compress_thought_tags(text, config)
        
        assert "<thought>" not in result
        assert "然后执行命令" in result


class TestBashOutputCompression:
    """Bash 输出压缩测试"""
    
    def test_short_output_unchanged(self):
        """短输出不变"""
        config = CompressionConfig()
        text = "Hello World"
        
        result = compress_bash_output(text, config)
        
        assert result == text
    
    def test_long_output_truncated(self):
        """长输出截断"""
        config = CompressionConfig(truncate_threshold=100, preserve_head_tail=20)
        text = "A" * 200
        
        result = compress_bash_output(text, config)
        
        assert len(result) < len(text)
        assert "truncated" in result.lower()
        assert result.startswith("AAAA")
        assert result.endswith("AAAA")
    
    def test_error_output_unchanged(self):
        """错误输出不截断"""
        config = CompressionConfig()
        text = "[ERROR] Something went wrong" * 100
        
        result = compress_bash_output(text, config)
        
        # 错误输出不截断，所以保持原样
        assert len(result) == len(text)


class TestObservationCompression:
    """观察结果压缩测试"""
    
    def test_compress_successful_output(self):
        """压缩成功输出"""
        config = CompressionConfig(truncate_threshold=50, preserve_head_tail=10)
        observation = {
            "role": "tool",
            "content": "<returncode>0</returncode>\n<output>\n" + "x" * 200 + "\n</output>",
        }
        
        result = compress_observation(observation, config)
        
        assert result["content"] != observation["content"]
        assert "truncated" in result["content"].lower()
    
    def test_preserve_error_output(self):
        """保留错误输出"""
        config = CompressionConfig()
        observation = {
            "role": "tool",
            "content": "<returncode>1</returncode>\n<output>\nERROR\n</output>",
        }
        
        result = compress_observation(observation, config)
        
        # 错误输出不压缩
        assert "ERROR" in result["content"]


class TestMessagesCompression:
    """消息列表压缩测试"""
    
    def test_compress_full_conversation(self):
        """压缩完整对话"""
        config = CompressionConfig(compress_thought=True)
        messages = [
            {"role": "system", "content": "You are a helpful assistant"},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "<thought>我需要回答用户的问题</thought>Hello!"},
            {
                "role": "tool",
                "content": "<returncode>0</returncode>\n<output>\n" + "x" * 1000 + "\n</output>",
            },
        ]
        
        result = compress_messages(messages, config)
        
        # 验证压缩效果
        assert len(result) == len(messages)
        
        # 检查 thought 被压缩
        assistant_content = result[2]["content"]
        assert "<thought>" not in assistant_content
        assert "<think>" in assistant_content or assistant_content == "Hello!"


class TestCompressionStats:
    """压缩统计测试"""
    
    def test_token_estimation(self):
        """Token 估算"""
        text = "Hello World" * 100
        tokens = estimate_tokens(text)
        
        assert tokens == len(text) // 4
    
    def test_savings_calculation(self):
        """节省计算"""
        original = [
            {"role": "user", "content": "x" * 1000},
            {"role": "assistant", "content": "y" * 1000},
        ]
        compressed = [
            {"role": "user", "content": "x" * 500},
            {"role": "assistant", "content": "y" * 500},
        ]
        
        stats = compute_compression_stats(original, compressed)
        
        assert stats.savings_percent > 0
        assert stats.messages_compressed == 2


# ============================================================================
# 优化缓存测试
# ============================================================================

class TestOptimizedCache:
    """优化缓存测试"""
    
    def test_exact_hit(self):
        """精确匹配命中"""
        cache = OptimizedCache()
        messages = [{"role": "user", "content": "test"}]
        
        cache.set(messages, {"result": "data"})
        result = cache.get(messages)
        
        assert result == {"result": "data"}
        assert cache.get_stats()["exact_hits"] == 1
    
    def test_window_cache(self):
        """窗口缓存命中"""
        config = OptimizedCacheConfig(cache_by_task=True, turn_window=2)
        cache = OptimizedCache(config)
        
        # 模拟对话: system + user + assistant + tool
        messages1 = [
            {"role": "system", "content": "You are helpful"},
            {"role": "user", "content": "task1"},
            {"role": "assistant", "content": "response1"},
            {"role": "tool", "content": "result1"},
        ]
        
        messages2 = [
            {"role": "system", "content": "You are helpful"},
            {"role": "user", "content": "task1"},  # 相同任务
            {"role": "assistant", "content": "response1"},  # 相同回复
            {"role": "tool", "content": "result2"},  # 不同结果
        ]
        
        cache.set(messages1, {"result": "data1"})
        result = cache.get(messages2)
        
        # 应该命中 (忽略 tool 结果差异)
        assert result is not None
    
    def test_semantic_cache(self):
        """语义缓存命中"""
        config = OptimizedCacheConfig(use_semantic_cache=True, similarity_threshold=0.6)
        cache = OptimizedCache(config)
        
        messages1 = [{"role": "user", "content": "How do I fix the bug in my code?"}]
        messages2 = [{"role": "user", "content": "How can I fix the bug in my program?"}]
        
        cache.set(messages1, {"result": "data"})
        result = cache.get(messages2)
        
        # 语义相似，应该命中
        assert result is not None
    
    def test_stats(self):
        """统计"""
        cache = OptimizedCache()
        messages = [{"role": "user", "content": "test"}]
        
        cache.get(messages)  # miss
        cache.set(messages, {"data": 1})
        cache.get(messages)  # hit
        cache.get(messages)  # hit
        
        stats = cache.get_stats()
        assert stats["misses"] == 1
        assert stats["exact_hits"] == 2
        assert "hit_rate" in stats


class TestCacheEviction:
    """缓存淘汰测试"""
    
    def test_lru_eviction(self):
        """LRU 淘汰"""
        config = OptimizedCacheConfig(max_entries=3)
        cache = OptimizedCache(config)
        
        # 填充缓存
        for i in range(5):
            cache.set([{"role": "user", "content": f"msg{i}"}], {"result": i})
        
        # 应该有 3 个条目
        total = sum(cache.get_stats()["cache_size"].values())
        assert total <= config.max_entries


# ============================================================================
# 运行
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
