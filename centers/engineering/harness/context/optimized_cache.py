"""
优化缓存 - Phase 优化 v2
核心: 基于轮次的智能缓存策略

策略:
1. Turn-level Cache: 只缓存"任务 + 前 N 轮"的响应模式
2. Semantic相似度: 简单 token 重叠匹配
3. Response Template: 缓存响应结构而非具体内容
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("optimized_cache")


# ============================================================================
# 配置
# ============================================================================

@dataclass
class OptimizedCacheConfig:
    """优化缓存配置"""
    # 基础
    ttl: int = 300                    # TTL 秒
    max_entries: int = 500            # 最大条目
    
    # 滑动窗口
    turn_window: int = 2              # 考虑最近 N 轮
    cache_by_task: bool = True        # 按任务缓存
    
    # 相似度
    similarity_threshold: float = 0.85  # 相似度阈值
    use_semantic_cache: bool = True   # 启用语义缓存
    
    # 乐观缓存 (experimental)
    optimistic_cache: bool = False     # 预测性缓存


@dataclass
class CacheEntry:
    """缓存条目"""
    key: str
    response: Any
    timestamp: float
    access_count: int = 0
    last_access: float = field(default_factory=time.time)
    hit_count: int = 0
    
    def is_expired(self, ttl: int) -> bool:
        return time.time() - self.timestamp > ttl


# ============================================================================
# 优化缓存
# ============================================================================

class OptimizedCache:
    """
    优化缓存 - 多层缓存策略
    
    Level 1: 精确匹配 (原有逻辑)
    Level 2: 滑动窗口匹配
    Level 3: 语义相似匹配
    """
    
    def __init__(self, config: OptimizedCacheConfig | None = None):
        self.config = config or OptimizedCacheConfig()
        self._exact_cache: dict[str, CacheEntry] = {}     # 精确匹配
        self._window_cache: dict[str, CacheEntry] = {}   # 窗口匹配
        self._semantic_cache: dict[str, CacheEntry] = {}  # 语义匹配
        
        # 统计
        self.stats = {
            "exact_hits": 0,
            "window_hits": 0,
            "semantic_hits": 0,
            "misses": 0,
            "sets": 0,
            "evictions": 0,
        }
    
    # =========================================================================
    # Key 生成
    # =========================================================================
    
    def _make_task_key(self, messages: list[dict]) -> str:
        """从 messages 中提取任务标识"""
        # 策略: 取 user 消息的 content 作为任务标识
        user_contents = []
        for msg in messages:
            if msg.get("role") == "user":
                content = msg.get("content", "")
                # 只取前 200 字符
                user_contents.append(content[:200])
        
        # 如果有 system message，也包含
        for msg in messages:
            if msg.get("role") == "system":
                content = msg.get("content", "")[:200]
                user_contents.insert(0, f"SYS:{content}")
        
        return "|".join(user_contents)
    
    def _make_turn_key(self, messages: list[dict]) -> str:
        """
        生成轮次级别的 key
        
        策略: 只 hash 最近 N 轮的内容
        这样中间轮次变化不会影响缓存命中
        """
        # 找到最后一个 assistant 消息的位置
        last_assistant_idx = -1
        for i in range(len(messages) - 1, -1, -1):
            if messages[i].get("role") == "assistant":
                last_assistant_idx = i
                break
        
        if last_assistant_idx == -1:
            # 没有 assistant 消息，使用全部
            return self._make_exact_key(messages)
        
        # 只取最近 N 轮
        window_size = self.config.turn_window * 2  # 2 messages per turn
        start_idx = max(0, last_assistant_idx - window_size)
        recent = messages[start_idx:]
        
        # 生成 key
        return self._make_content_hash(recent)
    
    def _make_exact_key(self, messages: list[dict]) -> str:
        """精确 key"""
        contents = [m.get("content", "") for m in messages]
        return hashlib.sha256(
            json.dumps(contents, sort_keys=True).encode()
        ).hexdigest()[:24]
    
    def _make_content_hash(self, messages: list[dict]) -> str:
        """内容 hash"""
        contents = []
        for m in messages:
            role = m.get("role", "")
            content = m.get("content", "")
            # 简化: 只 hash content，忽略 tool_call_id 等
            if role == "tool":
                # tool 消息不参与 hash (因为每次执行结果不同)
                continue
            contents.append(f"{role}:{content[:100]}")
        
        combined = "\n".join(contents)
        return hashlib.sha256(combined.encode()).hexdigest()[:24]
    
    def _compute_similarity(self, texts: list[str], cached_texts: list[str]) -> float:
        """
        计算相似度 (简单 token 重叠)
        
        Jaccard similarity: |A ∩ B| / |A ∪ B|
        """
        if not texts or not cached_texts:
            return 0.0
        
        # Tokenize
        text_set = set()
        for t in texts:
            text_set.update(t.lower().split())
        
        cached_set = set()
        for t in cached_texts:
            cached_set.update(t.lower().split())
        
        if not text_set or not cached_set:
            return 0.0
        
        intersection = text_set & cached_set
        union = text_set | cached_set
        
        return len(intersection) / len(union)
    
    # =========================================================================
    # 缓存操作
    # =========================================================================
    
    def get(self, messages: list[dict]) -> Any | None:
        """获取缓存"""
        # Level 1: 精确匹配
        exact_key = self._make_exact_key(messages)
        if exact_key in self._exact_cache:
            entry = self._exact_cache[exact_key]
            if not entry.is_expired(self.config.ttl):
                entry.hit_count += 1
                entry.last_access = time.time()
                self.stats["exact_hits"] += 1
                logger.debug(f"Cache HIT (exact): {exact_key[:12]}...")
                return entry.response
            else:
                # 过期删除
                del self._exact_cache[exact_key]
        
        # Level 2: 窗口匹配
        if self.config.cache_by_task:
            turn_key = self._make_turn_key(messages)
            if turn_key in self._window_cache:
                entry = self._window_cache[turn_key]
                if not entry.is_expired(self.config.ttl):
                    entry.hit_count += 1
                    entry.last_access = time.time()
                    self.stats["window_hits"] += 1
                    logger.debug(f"Cache HIT (window): {turn_key[:12]}...")
                    return entry.response
        
        # Level 3: 语义匹配
        if self.config.use_semantic_cache:
            # 提取当前任务的文本
            current_texts = [m.get("content", "") for m in messages if m.get("role") == "user"]
            
            for key, entry in self._semantic_cache.items():
                if entry.is_expired(self.config.ttl):
                    continue
                
                cached_texts = [m.get("content", "") for m in entry.response.get("messages", []) if m.get("role") == "user"]
                
                similarity = self._compute_similarity(current_texts, cached_texts)
                
                if similarity >= self.config.similarity_threshold:
                    entry.hit_count += 1
                    entry.last_access = time.time()
                    self.stats["semantic_hits"] += 1
                    logger.debug(f"Cache HIT (semantic, sim={similarity:.2f}): {key[:12]}...")
                    return entry.response
        
        # Miss
        self.stats["misses"] += 1
        logger.debug("Cache MISS")
        return None
    
    def set(self, messages: list[dict], response: Any):
        """设置缓存"""
        # 精确缓存
        exact_key = self._make_exact_key(messages)
        self._exact_cache[exact_key] = CacheEntry(
            key=exact_key,
            response=response,
            timestamp=time.time(),
        )
        
        # 窗口缓存
        if self.config.cache_by_task:
            turn_key = self._make_turn_key(messages)
            # 只在窗口 key 不存在时设置 (避免覆盖)
            if turn_key not in self._window_cache:
                self._window_cache[turn_key] = CacheEntry(
                    key=turn_key,
                    response=response,
                    timestamp=time.time(),
                )
        
        # 语义缓存 (只对 user 消息少的场景)
        if self.config.use_semantic_cache:
            user_contents = [m.get("content", "") for m in messages if m.get("role") == "user"]
            if len(user_contents) <= 3:  # 只对短对话做语义缓存
                semantic_key = hashlib.sha256(
                    " ".join(user_contents).encode()
                ).hexdigest()[:16]
                if semantic_key not in self._semantic_cache:
                    self._semantic_cache[semantic_key] = CacheEntry(
                        key=semantic_key,
                        response={"messages": messages, "response": response},
                        timestamp=time.time(),
                    )
        
        # LRU 淘汰
        self._evict_if_needed()
        self.stats["sets"] += 1
    
    def _evict_if_needed(self):
        """LRU 淘汰"""
        total_entries = (
            len(self._exact_cache) + 
            len(self._window_cache) + 
            len(self._semantic_cache)
        )
        
        if total_entries <= self.config.max_entries:
            return
        
        # 找出最旧的条目
        all_entries = []
        for cache in [self._exact_cache, self._window_cache, self._semantic_cache]:
            for key, entry in cache.items():
                all_entries.append((entry.last_access, key, cache))
        
        # 按访问时间排序
        all_entries.sort(key=lambda x: x[0])
        
        # 删除最旧的 10%
        to_remove = total_entries - int(self.config.max_entries * 0.8)
        for _, key, cache in all_entries[:to_remove]:
            del cache[key]
            self.stats["evictions"] += 1
    
    def clear(self):
        """清空所有缓存"""
        self._exact_cache.clear()
        self._window_cache.clear()
        self._semantic_cache.clear()
        logger.info("Cache cleared")
    
    def get_stats(self) -> dict:
        """获取统计"""
        total_hits = (
            self.stats["exact_hits"] + 
            self.stats["window_hits"] + 
            self.stats["semantic_hits"]
        )
        total_requests = total_hits + self.stats["misses"]
        
        return {
            **self.stats,
            "total_hits": total_hits,
            "total_requests": total_requests,
            "hit_rate": f"{total_hits / total_requests * 100:.1f}%" if total_requests else "N/A",
            "cache_size": {
                "exact": len(self._exact_cache),
                "window": len(self._window_cache),
                "semantic": len(self._semantic_cache),
            },
        }
