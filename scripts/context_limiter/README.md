# POST 上下文限制集成指南

## 文件说明
- `fs_wrapper.py` – 文件操作包装器，需在调用实际文件操作前执行。
- `configure_limits.sh` – 查看/修改阈值（文件数/token数）。
- `monitor_context.sh` – 查看最近拒绝/允许的操作。
- `update_model_config.py` – 更新 OpenClaw 模型上下文窗口（可选）。

## 集成方法
在您的工具（如 `fs_guardian.py`、`knowledge_market.py`）中，在执行实际文件读写前调用包装器：

```python
import subprocess
result = subprocess.run(
    ['python3', 'scripts/context_limiter/fs_wrapper.py', agent_id, action] + file_list,
    capture_output=True, text=True
)
if result.returncode != 0:
    print(result.stderr)
    return  # 拒绝操作
# 继续实际文件操作...
# 弹性扩展
# 当模型上下文窗口增大时，只需修改 config/context_limits.json 中的 max_tokens 值，无需修改脚本。

# 验证
# 运行 ./monitor_context.sh 查看日志。
