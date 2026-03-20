# SWE-agent 快速参考
# Xuzhi-Lambda-Ergo 工学部

---

## 核心架构

```
Agent ←→ HistoryProcessor ←→ Model
           ↓
        ToolHandler ←→ Environment
           ↓
        Bash | Edit | Submit
```

## 历史处理

```yaml
history_processors:
  - type: last_n_observations
    n: 5              # 保留最近5条观察
    polling: 1        # 每步更新
```

## 模板变量

| 变量 | 用途 |
|------|------|
| `{{observation}}` | 当前观察 |
| `{{max_observation_length}}` | 最大观察长度 |
| `{{elided_chars}}` | 省略字符数 |
| `{{bash_stdout}}` | Bash 标准输出 |
| `{{bash_stderr}}` | Bash 标准错误 |

## 工具配置

```yaml
tools:
  bundles:
    - path: tools/registry
    - path: tools/edit_anthropic
    - path: tools/review_on_submit_m
  env_variables:
    PAGER: cat
    GIT_PAGER: cat
    TQDM_DISABLE: "1"
```

## 模型配置

```yaml
model:
  name: gpt-4o
  temperature: 0.0
  per_instance_cost_limit: 3.0
  retry:
    retries: 20
    min_wait: 10
    max_wait: 120
  delay: 0.0
  max_input_tokens: 128000
  max_output_tokens: 8192
```

## 重试机制

```python
RETRY_WITH_OUTPUT_TOKEN = "###SWE-AGENT-RETRY-WITH-OUTPUT###"
RETRY_WITHOUT_OUTPUT_TOKEN = "###SWE-AGENT-RETRY-WITHOUT-OUTPUT###"
EXIT_FORFEIT_TOKEN = "###SWE-AGENT-EXIT-FORFEIT###"
```

## 观察截断

```python
max_observation_length: int = 100_000  # 字符级截断
# 超过时输出:
# "Observation: <truncated><response clipped><NOTE>...chars elided...</NOTE>"
```

## Tag 机制

```python
{"content": "...", "tags": ["keep_output"]}   # 强制保留
{"content": "...", "tags": ["remove_output"]} # 强制删除
{"content": "...", "tags": ["is_demo"]}        # 是示范
```

## Agent 类型

| 类型 | 类 | 用途 |
|------|-----|------|
| default | `DefaultAgent` | 标准单轮 |
| retry | `RetryAgent` | 重试循环 |
| shell | `ShellAgent` | Shell 专用 |

## 错误类型

```python
ContentPolicyViolationError  # 内容违规
ContextWindowExceededError   # 上下文超限
CostLimitExceededError       # 成本超限
FormatError                  # 格式错误
CommandTimeoutError          # 命令超时
```

## 关键文件

| 文件 | 职责 |
|------|------|
| `sweagent/agent/agents.py` | Agent 主逻辑 |
| `sweagent/agent/history_processors.py` | 历史压缩 |
| `sweagent/agent/models.py` | 模型抽象 (Litellm) |
| `sweagent/environment/swe_env.py` | 沙盒环境 |
| `sweagent/tools/parsing.py` | 动作解析 |
| `sweagent/tools/tools.py` | 工具处理器 |

## Jinja2 模板

```yaml
system_template: |
  You are a helpful assistant...

instance_template: |
  I've uploaded {{working_dir}}...

next_step_template: |
  Observation: {{observation}}

next_step_truncated_observation_template: |
  Observation: {{observation[:max_observation_length]}}<response clipped>
  <NOTE>{{elided_chars}} characters were elided...</NOTE>
```
