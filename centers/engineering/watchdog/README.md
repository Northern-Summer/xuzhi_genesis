# Watchdog System — 安全监控/异常检测

## 概述

Watchdog 是虚质系统的安全监控层，负责在 OpenClaw Gateway 异常时自动恢复。

## 核心组件

### 1. watchdog.sh
系统级 watchdog 脚本，不依赖 OpenClaw cron。

**功能：**
- `is_healthy()` — 检查 Gateway /health 端点
- `check_auth_token()` — 检测 OpenClaw auth token 状态
- `check_lambda_session()` — 检查 Λ 主会话是否存活
- `request_lambda_precheckpoint()` — 重启前请求 Λ 保存任务状态
- `wait_for_checkpoint()` — 等待 Λ 写入 checkpoint
- `wake_lambda_with_restore()` — 重启后唤醒 Λ 恢复任务

**流程：**
```
健康检查 → 正常 → 记录Lambda会话状态 → 退出
        → 异常 → 预checkpoint → 重启Gateway → 等待启动
               → 唤醒Lambda → 验证恢复 → 记录日志
```

**阈值：**
- `MAX_RESTARTS_PER_HOUR=3` — 每小时最多重启3次，超限停止
- `PRECHECK_TIMEOUT=15s` — 等待 Λ checkpoint 的超时
- `GATEWAY_STARTUP=15s` — Gateway 重启后等待就绪时间

### 2. health_check.sh
健康检查脚本，输出自然语言状态报告。

**检查项：**
- 智能体社会评价（ratings.json）
- 任务中心状态（tasks.json）
- 唤醒队列（queue.json）
- API 配额使用（quota_usage.json）
- 最近唤醒日志

**用法：**
```bash
bash ~/xuzhi_genesis/centers/engineering/health_check.sh
```

### 3. death_detector.py
Agent 死亡检测器（独立 Python 脚本）。

### 4. self_heal_*.py
自愈脚本系列：
- `self_heal_auto_autorra.py` — AutoRA 异常自愈
- `self_heal_delta.py` — Δ 专项自愈

## 测试

```bash
# 运行所有测试（80 passed）
cd ~/xuzhi_genesis/centers/engineering
python3 -m pytest harness/tests/ -v --tb=short

# 单独测试 watchdog 相关逻辑
python3 -m pytest harness/tests/test_phase4.py -v

# 语法检查
bash -n watchdog.sh && echo "watchdog.sh OK"
```

## 已知问题

- test_phase3.py 曾有 `ImportError: cannot import name 'HarnessAgent'` — 已修复（改为 `from harness.harness import`）
- `asyncio.get_event_loop()` 在 Python 3.12+ 触发 DeprecationWarning — 不影响功能

## 维护者

Engineering Center (Λ/Δ)
