# mini-SWE-agent 深度研究
## Deep Dive Research Document
**Source**: https://github.com/SWE-agent/mini-SWE-agent  
**Date**: 2026-03-20

---

## 核心发现

### 1. 极简架构 (vs SWE-agent)

mini-SWE-agent 删除了 SWE-agent 中 15+ 个复杂组件，只保留 **5 个核心组件**：

```
agents/default.py     → Agent.simple_loop() [155 行]
environments/local.py → LocalEnvironment.bash()
models/litellm_model.py → LitellmModel (litellm 封装)
tools/bash.py         → TOOLS["bash"]
exceptions.py         → InterruptAgentFlow 异常体系
```

**vs SWE-agent**:
- SWE-agent: history_processors, custom_models, remote_env, tools/repo_search, tools/documentation_search, tools/web_search, tools/file_search, tools/index, ...
- mini-SWE-agent: **只有 bash**

### 2. Interrupt-based 控制流

SWE-agent 家族使用 **异常作为控制流**：

```python
# exceptions.py
class InterruptAgentFlow(Exception):
    """Raised to interrupt the agent flow and add messages."""
    def __init__(self, *messages: dict):
        self.messages = messages

class Submitted(InterruptAgentFlow):
    """Raised when the agent has completed its task."""

class LimitsExceeded(InterruptAgentFlow):
    """Raised when the agent has exceeded its cost or step limit."""

class UserInterruption(InterruptAgentFlow):
    """Raised when the user interrupts the agent."""

class FormatError(InterruptAgentFlow):
    """Raised when the LM's output is not in the expected format."""
```

**优势**: 可以在任意深度调用栈中终止并返回消息给模型

### 3. Agent.simple_loop()

```python
def simple_loop(self, config, instance):
    messages = [instance.initial_message]
    
    for step in scipy.logspace(0, np.log10(config.max_steps), base=10).astype(int).unique():
        message = self.model.query(messages)
        actions = message["extra"]["actions"]
        messages.append(message)
        
        outputs = self.environment.execute(actions)
        formatted = self.model.format_observation_messages(message, outputs)
        messages.extend(formatted)
```

**注意**: 使用 `scipy.logspace` 决定检查点的步骤数 (非均匀分布)

### 4. Jinja2 观察模板

```python
observation_template = (
    "{% if output.exception_info %}<exception>{{output.exception_info}}</exception>\n{% endif %}"
    "<returncode>{{output.returncode}}</returncode>\n<output>\n{{output.output}}</output>"
)
```

使用 Jinja2 模板动态渲染观察结果，支持条件渲染 (exception_info)

### 5. FormatError 自修复机制

```python
# models/litellm_model.py
format_error_template: str = "{{ error }}"

def _parse_actions(self, response):
    if not tool_calls:
        raise FormatError({
            "role": "user",
            "content": "No tool calls found. Every response MUST include at least one tool call.",
            "extra": {"interrupt_type": "FormatError"},
        })
```

当模型输出不包含 tool_calls 时，抛出 FormatError，下一轮模型会收到错误消息并重新生成

### 6. Litellm 模型抽象

```python
class LitellmModel:
    def __init__(self, *, config_class: Callable = LitellmModelConfig, **kwargs):
        self.config = config_class(**kwargs)
    
    def query(self, messages: list[dict[str, str]], **kwargs) -> dict:
        response = litellm.completion(
            model=self.config.model_name,
            messages=messages,
            tools=[BASH_TOOL],  # 只传递 BASH_TOOL
            **self.config.model_kwargs,
        )
        # 解析 actions, 计算 cost, 返回标准化消息
```

**支持**: OpenAI, Anthropic, Azure, Google, AWS, Local models 等

### 7. 观察结果格式化

```python
def format_toolcall_observation_messages(
    *,
    actions: list[dict],
    outputs: list[dict],
    observation_template: str,
) -> list[dict]:
    results = []
    for action, output in zip(actions, padded_outputs):
        content = Template(observation_template, undefined=StrictUndefined).render(
            output=output, **(template_vars or {})
        )
        msg = {
            "content": content,
            "role": "tool",
            "tool_call_id": action["tool_call_id"],
            "extra": {"raw_output": output.get("output", ""), ...}
        }
        results.append(msg)
    return results
```

---

## 与 SWE-agent 的对比

| 特性 | SWE-agent | mini-SWE-agent |
|------|-----------|----------------|
| 架构复杂度 | 高度模块化 (15+ 组件) | 极简 (5 核心组件) |
| History 处理 | 复杂的多 processor 体系 | 无 (只追加) |
| 环境 | 可配置 (local/cloud/remote) | 只有 local bash |
| 模型 | 需要 custom wrapper | litellm 统一接口 |
| 工具 | 多种工具 (search, index, doc) | 只有 bash |
| 配置 | 多层配置系统 | 简单 config.yaml |

---

## 对 Harness 的启示

### 1. 保留核心，简化架构

Harness 应该：
- ✅ **保留**: history processor 框架, truncation, guards
- ❌ **简化**: 不需要复杂的工具注册系统
- ❌ **可选**: litellm 封装 (取决于是否需要多模型支持)

### 2. Interrupt-based 控制流

考虑引入 `InterruptAgentFlow` 模式：
```python
class HarnessInterrupt(Exception):
    """Base interrupt for harness flow"""
    pass

class TaskCompleted(HarnessInterrupt): pass
class StepLimitExceeded(HarnessInterrupt): pass
class FormatError(HarnessInterrupt): pass
```

### 3. 观察模板 Jinja2 化

将硬编码的字符串模板替换为 Jinja2：
```python
observation_template = Environment(loader=StrictUndefined).from_string(
    "{% if output.exception_info %}<exception>{{output.exception_info}}</exception>\n{% endif %}"
    "<returncode>{{output.returncode}}</returncode>\n<output>\n{{output.output}}</output>"
)
```

### 4. 模型抽象层 (可选)

如果需要多模型支持，使用 litellm：
```python
# Dependencies: litellm >= 1.75.5
from litellm import completion

response = completion(
    model="anthropic/claude-sonnet-4-5-20250929",
    messages=messages,
    tools=[BASH_TOOL],
)
```

---

## 关键文件清单

```
mini-swe-agent/
├── src/minisweagent/
│   ├── agents/default.py         # 核心 Agent 类 [155 行]
│   ├── environments/local.py      # 本地 bash 环境
│   ├── models/
│   │   ├── __init__.py
│   │   ├── litellm_model.py       # LitellmModel
│   │   └── utils/
│   │       ├── actions_toolcall.py  # 解析 tool calls
│   │       ├── anthropic_utils.py   # Anthropic 特定处理
│   │       ├── cache_control.py     # 缓存控制
│   │       ├── openai_multimodal.py # 多模态处理
│   │       └── retry.py             # 重试逻辑
│   ├── tools/
│   │   ├── __init__.py
│   │   └── bash.py               # bash 工具定义
│   ├── exceptions.py             # InterruptAgentFlow
│   └── run/
│       ├── mini.py               # CLI 入口
│       └── utilities/
│           ├── mini_extra.py     # 额外工具
│           └── config.py         # 配置管理
├── pyproject.toml
└── README.md
```

---

## 依赖分析

```python
dependencies = [
    "pyyaml",              # 配置
    "requests",            # HTTP
    "jinja2",              # 模板
    "pydantic >= 2.0",     # 数据验证
    "litellm >= 1.75.5",   # 多模型抽象
    "tenacity",            # 重试
    "rich",                # 终端 UI
    "python-dotenv",       # 环境变量
    "typer",               # CLI
    "platformdirs",        # 平台目录
    "textual",             # TUI
    "prompt_toolkit",      # CLI 交互
    "datasets",            # 数据集
]
```

---

## 下一步行动

1. **更新 Harness 架构**: 整合 InterruptAgentFlow 模式
2. **简化工具系统**: 只保留 bash + 必要的 guards
3. **引入 Jinja2 模板**: 动态渲染观察结果
4. **评估 litellm**: 是否需要多模型支持

---

## 参考链接

- [mini-SWE-agent GitHub](https://github.com/SWE-agent/mini-SWE-agent)
- [mini-SWE-agent Documentation](https://mini-swe-agent.com/latest/)
- [litellm 文档](https://docs.litellm.ai/)
- [SWE-agent vs mini-SWE-agent 对比](https://github.com/SWE-agent/mini-SWE-agent?tab=readme-ov-file#differences-to-swe-agent)
