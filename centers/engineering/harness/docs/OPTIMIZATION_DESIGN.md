# 缓存效率优化方案
## 诊断：为什么缓存命中率低？

### 当前问题
```
缓存 key = SHA256(all messages content) = 精确匹配
问题：每轮对话产生新内容 → key 永远不同 → 缓存失效
```

### 优化矩阵

| 策略 | 预期提升 | 风险 | 实现复杂度 |
|------|----------|------|------------|
| **滑动窗口缓存** | +15-20% | 低 | 中 |
| **Semantic Caching** | +20-30% | 中 | 高 |
| **Batched Actions** | -50% POST | 中 | 高 |
| **History 压缩 | +10-15% | 低 | 中 |
| **Thought Compression** | +5-10% | 低 | 低 |

## 策略 1: 滑动窗口缓存 (Sliding Window Cache)

### 核心思想
不缓存完整对话历史，只缓存**最近 N 轮**的模式。

```
对话结构:
[System] [User: task] [Assistant: thought] [Tool: result] [Assistant: thought] [Tool: result]
                                              ↑___________滑动窗口___________↑
缓存 key: hash(任务 + 最后3轮交互模式)
```

### 实现
```python
class SlidingWindowCache:
    def __init__(self, window_size: int = 3):
        self.window_size = window_size
    
    def _make_key(self, messages: list[dict], task: str) -> str:
        # 只取最后 window_size 轮
        recent = messages[-self.window_size * 2:]  # 2 messages per turn
        content = task + "\n".join([m.get("content", "") for m in recent])
        return hashlib.sha256(content.encode()).hexdigest()[:24]
```

## 策略 2: Semantic Caching (语义缓存)

### 核心思想
用 embeddings 计算语义相似度，而非精确匹配。

```
相似度 > 0.95 → 命中缓存
相似度 0.80-0.95 → 使用缓存但标记为 uncertain
相似度 < 0.80 → 未命中
```

### 实现 (简化版)
```python
class SemanticCache:
    def __init__(self, similarity_threshold: float = 0.90):
        self.threshold = similarity_threshold
        self._cache: dict[str, dict] = {}
    
    def _compute_similarity(self, text1: str, text2: str) -> float:
        # 使用 TF-IDF 或简单的 token 重叠
        tokens1 = set(text1.split())
        tokens2 = set(text2.split())
        intersection = tokens1 & tokens2
        union = tokens1 | tokens2
        return len(intersection) / len(union) if union else 0
```

## 策略 3: Batched Actions (批量动作)

### 核心思想
一次 POST 让模型输出多个动作，减少往返次数。

```
当前: User → POST → Assistant(action) → Execute → POST → Assistant(action) → ...
优化: User → POST → Assistant([action1, action2, action3]) → Execute all → POST → ...

减少: N 次往返 → 1 次往返
```

### 实现
```python
class BatchedLoop:
    def __init__(self, max_batch_size: int = 5):
        self.max_batch_size = max_batch_size
    
    def query_with_batch(self, messages: list[dict]) -> list[dict]:
        response = model.query(messages)
        # 解析多个 actions
        actions = response.get("extra", {}).get("actions", [])
        
        if len(actions) > 1:
            # 批量执行
            outputs = execute_all(actions)
            # 返回所有观察结果作为一条消息
            return [self._format_batch_obs(actions, outputs)]
        return [response]
```

## 策略 4: Thought Compression (思考压缩)

### 核心思想
用特殊标记替代冗长的思考过程。

```
当前: <thought>我需要先查看目录结构，然后读取文件，最后修改代码...</thought>
优化: <think step="1" action="explore"/> 或直接省略 thought
```

### mini-SWE-agent 的做法
mini-SWE-agent 完全没有 `<thought>` 标签，直接输出工具调用！

## 策略 5: Turn-level Caching (轮次缓存)

### 核心思想
缓存基于**轮次 (turn)** 而非整个对话。

```
Turn 1: User query → Assistant response (cached by task hash)
Turn 2: Task + Turn1 output → Turn2 response (cached by task+turn1 hash)
Turn 3: Task + Turn1 + Turn2 → Turn3 response (cached by task+turn2 hash)

问题: Turn3 的缓存 key 包含 Turn2 的输出 → still unique
解决: 只缓存 tool call pattern，不缓存执行结果
```

## 推荐实施方案

### Phase A: 快速优化 (低风险，高回报)
1. **Thought Compression**: 删除/缩短 `<thought>` 标签
2. **History 压缩**: 在观察结果中删除 `returncode=0` 的冗余输出
3. **滑动窗口缓存**: 实现基于任务的缓存

### Phase B: 中期优化 (中等风险)
4. **Batched Actions**: 修改 simple_loop 支持批量执行
5. **Turn-level Cache**: 实现轮次级别的缓存策略

### Phase C: 长期优化 (高风险，高回报)
6. **Semantic Cache**: 引入 embedding 相似度匹配

## 预期效果

| 优化 | Token 节省 | POST 减少 | 实施难度 |
|------|------------|-----------|----------|
| Thought Compression | 10-20% | 0% | ★☆☆ |
| History 压缩 | 15-25% | 0% | ★☆☆ |
| 滑动窗口缓存 | 0% | 20-30% | ★★☆ |
| Batched Actions | 0% | 50%+ | ★★★ |
| Semantic Cache | 0% | 30-40% | ★★★ |
