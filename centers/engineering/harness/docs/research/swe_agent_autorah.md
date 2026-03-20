# 研究报告：SWE-agent & AutoRA 深度分析
# Xuzhi-Lambda-Ergo 工学部 · 工程中心
# 研究时间: 2026-03-20

---

## 一、SWE-agent 深度分析

### 1.1 核心架构

SWE-agent 是普林斯顿 NLP 团队开发的 **SOTA 软件工程智能体**，解决 SWE-bench 基准（真实 GitHub Issue 修复）。

**三层架构**:
```
Agent (大脑) ←→ Environment (沙盒) ←→ Tools (工具)
```

**核心模块**:
| 模块 | 路径 | 职责 |
|------|------|------|
| `sweagent/agent/agents.py` | Agent 主逻辑 | step/run/ retry loop |
| `sweagent/agent/history_processors.py` | 历史管理 | 压缩/截断/缓存控制 |
| `sweagent/agent/models.py` | 模型抽象 | Litellm 统一接口 |
| `sweagent/environment/` | 环境管理 | 沙盒/执行/状态 |
| `sweagent/tools/` | 工具集 | Bash/Edit/Registry/Submit |

### 1.2 历史处理器 (History Processors) ⭐

这是 SWE-agent 最值得借鉴的设计之一：

```python
# 核心接口
class AbstractHistoryProcessor(Protocol):
    def __call__(self, history: History) -> History: ...

# 默认处理器（不做处理）
class DefaultHistoryProcessor: ...

# 截断旧观察（论文中使用的经典方法）
class LastNObservations:
    n: int  # 保留最近 n 条观察
    polling: int = 1  # 每隔 polling 步更新
    always_remove_output_for_tags: set[str] = {"remove_output"}
    always_keep_output_for_tags: set[str] = {"keep_output"}
```

**关键洞察**:
- 观察被截断时，替换为 `"Old environment output: (n lines omitted)"`
- 支持 **tag 机制**：标记"必须保留"或"必须删除"的观察
- `polling` 参数用于优化 prompt caching（避免每次都改变历史）

### 1.3 模板系统 (Jinja2)

```python
class TemplateConfig(BaseModel):
    system_template: str        # 系统提示模板
    instance_template: str      # 实例模板（含 problem_statement）
    next_step_template: str      # 下一轮观察模板
    next_step_no_output_template: str  # 无输出时模板
    strategy_template: str | None
    demonstration_template: str | None
    demonstrations: list[Path]  # 示范轨迹
    put_demos_in_history: bool  # 示范是否进入历史
```

**默认 `default.yaml` 模板结构**:
```
system: "You are a helpful assistant that can interact with a computer..."
instance: <uploaded_files>{{working_dir}}</uploaded_files>
          I've uploaded a python code repository...
          Can you help me implement the necessary changes...?
          Follow steps: 1. Find relevant code 2. Reproduce error 3. Edit 4. Rerun 5. Edge cases
next_step: "OBSERVATION: {{observation}}"
```

### 1.4 工具系统

**工具注册表** (`tools/registry/`):
- 统一的工具管理框架
- 支持 `bin/` (可执行) + `lib/` (库)
- `config.yaml` 定义工具元数据

**核心工具**:
| 工具 | 路径 | 功能 |
|------|------|------|
| `bash_only` | 内置 | 执行 bash 命令 |
| `edit_anthropic` | `tools/edit_anthropic/` | 原子化文件编辑 |
| `review_on_submit` | `tools/review_on_submit_m/` | 提交前审核 |
| `submit` | `tools/submit/` | 提交修复 |

**Bash 工具配置**:
```yaml
tools:
  bundles:
    - path: tools/registry
    - path: tools/edit_anthropic
    - path: tools/review_on_submit_m
  env_variables:  # 禁用 pager 等
    PAGER: cat
    GIT_PAGER: cat
    PIP_PROGRESS_BAR: 'off'
    TQDM_DISABLE: '1'
```

### 1.5 模型层 (Litellm 集成)

```python
class GenericAPIModelConfig:
    name: str
    per_instance_cost_limit: float = 3.0
    total_cost_limit: float = 0.0
    temperature: float = 0.0
    api_base: str | None  # 支持自定义端点
    api_key: SecretStr | None
    retry: RetryConfig  # 重试配置
    delay: float  # 请求延迟（防速率限制）
    fallbacks: list[dict]  # 备用模型列表
    max_input_tokens: int | None
    max_output_tokens: int | None
```

**重试机制**:
```python
class RetryConfig:
    retries: int = 20
    min_wait: float = 10  # 指数退避最小
    max_wait: float = 120  # 指数退避最大
```

### 1.6 Agent 类型

| 类型 | 用途 |
|------|------|
| `DefaultAgent` | 标准单轮对话 |
| `RetryAgent` | 重试循环（失败后换配置重跑） |
| `ShellAgent` | Shell 专用交互 |

### 1.7 观察截断

```python
next_step_truncated_observation_template: str = (
    "Observation: {{observation[:max_observation_length]}}<response clipped>"
    "<NOTE>Observations should not exceeded {{max_observation_length}} characters. "
    "{{elided_chars}} characters were elided..."
)
max_observation_length: int = 100_000  # 字符级截断
```

### 1.8 提交审核机制

`review_on_submit` 工具在提交前强制检查：
1. 重跑 reproduction script
2. 移除 reproduction script
3. 还原测试文件
4. 确认 diff 正确性

---

## 二、AutoRA Falsificationism 深度分析

### 2.1 核心概念

AutoRA (Automated Research Assistant) 是一个**闭环科学研究框架**，falsificationism 是其"证伪"策略。

**基本思想**:
```
观察现有数据 → 训练损失预测器 → 找高损失区域 → 做新实验 → 循环
```

**数学表述**:
```
X' = argmax_X' Ĉ(M, X, Y, X')
其中:
  M = 当前最佳候选模型
  X, Y = 已探查的实验条件和结果
  X' = 待探查的新条件
  Ĉ = 预测损失的 MLP
```

### 2.2 关键组件

| 组件 | 职责 |
|------|------|
| **Sampler** | 识别高损失区域，提出新实验条件 |
| **Pooler** | 从候选空间中选择要探查的条件 |
| **Falsification Pooler** | 找最能"证伪"当前模型的实验 |
| **Loss Predictor** | MLP 预测模型在 X' 上的损失 |

### 2.3 应用于 Agent 的思考

**类比**:
- AutoRA: 科学研究 ↔ Agent: 任务解决
- Falsification: 找模型弱点 ↔ Agent: 找执行漏洞
- Loss: 预测 vs 实际 ↔ Agent: 计划 vs 结果

**可用于**:
- **自适应测试**：让 Agent 主动找自己方案的漏洞
- **失败预测**：在执行前预测可能失败的地方
- **主动学习**：选择最有信息量的下一步

---

## 三、对 Harness 工程的关键启示

### 3.1 立即采纳 (High Priority)

#### A. 历史处理器架构
当前 Harness 的 `context.py` 需要重构为 SWE-agent 风格：

```python
# 建议: harness/core/history.py
class AbstractHistoryProcessor(Protocol):
    def __call__(self, history: list[HistoryItem]) -> list[HistoryItem]: ...

class LastNObservations(AbstractHistoryProcessor):
    """保留最近 n 条观察，截断旧的"""
    n: int
    polling: int = 1
    
    def __call__(self, history):
        # 实现截断逻辑
        ...

class CacheControl(AbstractHistoryProcessor):
    """为最后 n 条消息启用 prompt caching"""
    last_n: int = 2
    
    def __call__(self, history):
        # 设置 cache_control
        ...
```

#### B. 观察截断 + 模板化
将 SWE-agent 的观察截断策略集成：

```python
class ObservationTruncator:
    max_length: int = 100_000
    
    def truncate(self, observation: str) -> tuple[str, int]:
        if len(observation) > self.max_length:
            return (observation[:self.max_length], 
                    len(observation) - self.max_length)
        return (observation, 0)
```

#### C. 环境变量安全配置
直接采纳 SWE-agent 的 `env_variables` 配置：

```python
SAFE_ENV = {
    "PAGER": "cat",
    "MANPAGER": "cat", 
    "LESS": "-R",
    "PIP_PROGRESS_BAR": "off",
    "TQDM_DISABLE": "1",
    "GIT_PAGER": "cat",
}
```

#### D. 提交前审核机制
类似 `review_on_submit_m`，为 Harness 添加**自我验证**：

```python
class PreCommitReview:
    """执行前的自我检查"""
    def review(self, action: Action) -> ReviewResult:
        # 1. 检查是否是破坏性操作
        # 2. 检查是否需要备份
        # 3. 检查权限
        # 4. 模拟执行验证
```

### 3.2 中期采纳 (Medium Priority)

#### E. Litellm 风格的模型抽象
为 Harness 支持多模型：

```python
# harness/core/models.py
class ModelConfig(BaseModel):
    name: str
    api_base: str | None
    api_key: str | None
    max_tokens: int
    temperature: float = 0.0
    retry: RetryConfig

# 支持: OpenAI, Anthropic, Local, Accelerator 等
```

#### F. 重试循环 (RetryAgent 模式)
当任务失败时，自动切换策略重试：

```python
class RetryLoop:
    strategies: list[AgentConfig]  # 不同策略配置
    max_attempts: int
    
    def run(self, task: Task) -> Result:
        for i, config in enumerate(self.strategies):
            try:
                return Agent(config).run(task)
            except RetryableError:
                continue
        raise MaxRetriesExceeded()
```

#### G. Tag 机制
为消息添加元数据标签：

```python
# 保留/删除标记
{"content": "...", "tags": ["keep_output"]}  # 强制保留
{"content": "...", "tags": ["remove_output"]}  # 强制删除
{"content": "...", "tags": ["reproducible"]}   # 可复现结果
```

### 3.3 长期思考 (Long Term)

#### H. AutoRA 式自我改进
```
Agent 执行 → 失败预测 → 高风险区域重点验证 → 自我修复
```

**架构**:
```
┌─────────────────────────────────────┐
│         Harness Core                │
│  ┌─────────┐  ┌──────────────────┐  │
│  │ 执行器  │→ │ 失败预测器 (MLP) │  │
│  └─────────┘  └──────────────────┘  │
│       ↑               ↑             │
│       └── 反馈循环 ←──┘             │
└─────────────────────────────────────┘
```

#### I. 示范学习 (Demonstrations)
SWE-agent 支持示范轨迹，Harness 应支持：
- 优质轨迹存储与回放
- 从失败中学习（保存失败案例）
- 策略库（不同任务类型的最优策略）

---

## 四、具体改进计划

### Phase 1: 核心增强 (立即)
1. ✅ 历史处理器框架（`LastNObservations`）
2. ✅ 观察截断器（`ObservationTruncator`）
3. ✅ 环境变量安全配置
4. ✅ 预执行审核（`PreCommitGuard`）

### Phase 2: 模型层升级 (短期)
1. 模型配置抽象（支持多 provider）
2. 重试循环实现
3. 成本追踪

### Phase 3: 智能进化 (中期)
1. 失败预测器
2. 自适应策略选择
3. 示范学习系统

---

## 五、SWE-agent 源码关键引用

### A. 入口点 (`sweagent/__main__.py`)
```python
# 典型的 agent.run() 循环
agent = Agent.from_config(config)
env = SWEEnv.from_config(env_config)
result = agent.run(
    problem_statement=problem_statement,
    env=env,
    output_dir=Path("trajectories"),
)
```

### B. Agent step 流程 (`sweagent/agent/agents.py`)
```python
class DefaultAgent(AbstractAgent):
    def step(self) -> StepOutput:
        # 1. 采样动作
        action = self.action_sampler.sample(self.history)
        # 2. 执行动作
        observation = self.tool_handler.execute(action)
        # 3. 处理历史
        self.history.add(action, observation)
        self.history = self.history_processor(self.history)
        return StepOutput(action=action, observation=observation)
```

### C. 配置加载 (`sweagent/utils/config.py`)
```python
# YAML 配置驱动
config = AgentConfig.model_validate(yaml.safe_load(config_file))
```

---

## 六、总结

| 项目 | 核心贡献 | Harness 借鉴 |
|------|---------|--------------|
| SWE-agent | 历史压缩/工具框架/模板系统 | ✅ 全部采纳 |
| AutoRA | 闭环证伪/损失预测 | 🔄 长期集成 |

**SWE-agent 是目前最完整的开源 Agent 工程参考**，其模块化设计、配置驱动、错误恢复机制都值得深入学习。

**下一步**: 将 Phase 1 改进集成到现有 Harness 代码。
