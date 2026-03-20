"""
历史压缩 - Phase 优化
核心: 减少观察结果的冗余 token

优化策略:
1. 成功输出截断: returncode=0 时，保留首尾
2. 冗余信息删除: 空输出、重复分隔符
3. 思考标签压缩: <thought>...</thought> → <think/>
"""

from __future__ import annotations

import re
from dataclasses import dataclass


# ============================================================================
# 配置
# ============================================================================

@dataclass
class CompressionConfig:
    """压缩配置"""
    max_output_chars: int = 8000       # 单个输出最大字符
    preserve_head_tail: int = 2000     # 保留首尾字符数
    remove_empty_output: bool = True   # 删除空输出
    compress_thought: bool = True       # 压缩 thought 标签
    remove_thought: bool = False       # 完全删除 thought (激进模式)
    
    # 阈值
    truncate_threshold: int = 5000     # 超过此长度才截断
    empty_threshold: int = 10         # 少于等于此字符视为空


# ============================================================================
# 压缩函数
# ============================================================================

def compress_thought_tags(text: str, config: CompressionConfig) -> str:
    """
    压缩或删除 <thought> 标签
    
    原始: <thought>我需要先查看目录结构...</thought>
    压缩: <think>查看目录</think>
    删除: (完全删除)
    """
    if config.remove_thought:
        # 激进模式: 完全删除
        return re.sub(r'<thought>.*?</thought>', '', text, flags=re.DOTALL)
    
    if config.compress_thought:
        # 压缩模式: 保留摘要
        def shorten_thought(match):
            content = match.group(1)
            # 取前 20 个字符作为摘要
            summary = content[:30].strip()
            if len(content) > 30:
                summary += "..."
            return f"<think>{summary}</think>"
        
        return re.sub(r'<thought>(.*?)</thought>', shorten_thought, text, flags=re.DOTALL)
    
    return text


def compress_bash_output(text: str, config: CompressionConfig) -> str:
    """
    压缩 bash 输出
    
    策略:
    1. 空输出 → 删除或标记
    2. 成功输出 (returncode=0) → 保留首尾，删除中间
    3. 错误输出 (returncode≠0) → 保留全部
    """
    # 空输出
    if len(text.strip()) <= config.empty_threshold:
        if config.remove_empty_output:
            return "[output truncated - empty]"
        return text
    
    # 长输出才截断
    if len(text) <= config.truncate_threshold:
        return text
    
    # 截断: 保留首尾
    head = text[:config.preserve_head_tail]
    tail = text[-config.preserve_head_tail:]
    
    removed = len(text) - len(head) - len(tail)
    
    return f"{head}\n\n[... {removed:,} characters truncated ...]\n\n{tail}"


def compress_observation(observation: dict, config: CompressionConfig | None = None) -> dict:
    """
    压缩单个观察结果
    
    输入:
    {
        "role": "tool",
        "content": "<returncode>0</returncode>\n<output>...</output>",
        "tool_call_id": "call_xxx",
    }
    
    输出: 压缩后的 observation
    """
    config = config or CompressionConfig()
    
    # 复制以避免修改原始数据
    obs = dict(observation)
    content = obs.get("content", "")
    
    # 1. 解析 returncode
    returncode_match = re.search(r'<returncode>(\d+)</returncode>', content)
    returncode = int(returncode_match.group(1)) if returncode_match else None
    
    # 2. 提取 output
    output_match = re.search(r'<output>(.*?)</output>', content, re.DOTALL)
    output = output_match.group(1) if output_match else content
    
    # 3. 提取 exception
    exception_match = re.search(r'<exception>(.*?)</exception>', content, re.DOTALL)
    exception = exception_match.group(1) if exception_match else None
    
    # 4. 压缩 output
    if returncode == 0 and not exception:
        # 成功输出 → 压缩
        output = compress_bash_output(output, config)
    # 失败输出 → 不压缩
    
    # 5. 重建 content
    parts = []
    if exception:
        parts.append(f"<exception>{exception}</exception>")
    if returncode is not None:
        parts.append(f"<returncode>{returncode}</returncode>")
    parts.append(f"<output>\n{output}\n</output>")
    
    obs["content"] = "\n".join(parts)
    
    # 6. 更新 extra (如果存在)
    if "extra" in obs and isinstance(obs["extra"], dict):
        obs["extra"]["compressed"] = True
        obs["extra"]["original_length"] = len(content)
        obs["extra"]["compressed_length"] = len(obs["content"])
    
    return obs


def compress_messages(messages: list[dict], config: CompressionConfig | None = None) -> list[dict]:
    """
    压缩整个消息列表
    
    遍历所有消息:
    - tool 角色: 压缩观察结果
    - assistant 角色: 压缩 thought 标签
    - 其他: 不变
    """
    config = config or CompressionConfig()
    compressed = []
    
    for msg in messages:
        msg_copy = dict(msg)
        
        if msg_copy.get("role") == "tool":
            # 压缩工具观察结果
            msg_copy = compress_observation(msg_copy, config)
        
        elif msg_copy.get("role") == "assistant":
            # 压缩 assistant 的 thought
            content = msg_copy.get("content", "")
            if isinstance(content, str):
                content = compress_thought_tags(content, config)
                msg_copy["content"] = content
        
        elif msg_copy.get("role") == "system":
            # 系统消息: 最小化压缩
            content = msg_copy.get("content", "")
            if isinstance(content, str) and config.compress_thought:
                content = compress_thought_tags(content, config)
                msg_copy["content"] = content
        
        compressed.append(msg_copy)
    
    return compressed


# ============================================================================
# 统计
# ============================================================================

@dataclass
class CompressionStats:
    """压缩统计"""
    original_tokens: int = 0
    compressed_tokens: int = 0
    messages_compressed: int = 0
    output_truncated: int = 0
    thought_compressed: int = 0
    
    @property
    def savings_percent(self) -> float:
        if self.original_tokens == 0:
            return 0
        return (1 - self.compressed_tokens / self.original_tokens) * 100
    
    def to_dict(self) -> dict:
        return {
            "original_tokens_approx": self.original_tokens,
            "compressed_tokens_approx": self.compressed_tokens,
            "savings_percent": f"{self.savings_percent:.1f}%",
            "messages_compressed": self.messages_compressed,
            "output_truncated": self.output_truncated,
            "thought_compressed": self.thought_compressed,
        }


def estimate_tokens(text: str) -> int:
    """估算 token 数量 (粗略: 1 token ≈ 4 字符)"""
    return len(text) // 4


def compute_compression_stats(
    original: list[dict],
    compressed: list[dict],
) -> CompressionStats:
    """计算压缩统计"""
    stats = CompressionStats()
    
    for orig, comp in zip(original, compressed):
        orig_content = orig.get("content", "")
        comp_content = comp.get("content", "")
        
        stats.original_tokens += estimate_tokens(orig_content)
        stats.compressed_tokens += estimate_tokens(comp_content)
        
        if orig_content != comp_content:
            stats.messages_compressed += 1
            
            # 检查是哪种压缩
            if len(orig_content) > len(comp_content):
                # 被压缩了
                if "<thought>" in orig_content and "<think>" in comp_content:
                    stats.thought_compressed += 1
                else:
                    stats.output_truncated += 1
    
    return stats
