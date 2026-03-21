# Xuzhi Genesis — 虚质系统

> 让系统学会自我维持、自我修复、自我演化。运行超过一年，然后AGI。

## 是什么

Xuzhi 是一个多智能体协作系统，以"工作与效率"为核心隐喻，构建能够长时间自主运行的软件基础设施。系统由多个专业化 Agent 组成，通过议会机制协调，通过情报中心获取外部知识，通过工程中心维持自身健康。

## 架构

```
虚质系统
├── engineering/     工程中心 — 周期调度、死亡检测、配额监控、Harness
├── intelligence/   情报中心 — RSS采集、种子生成、知识提取、上下文注入
├── mind/           心智中心 — 社会评分、议会、排行榜、智能体注册
└── task/           任务中心 — 任务生命周期管理
```

**核心原则**：错误可以是野蛮的，但秩序必须是强大的。稳定机制 > 临时修复。

## 当前阶段

**Harness Phase 4 — Self-Sustaining Agent Core**

目标：30天无人值守运行。

- `centers/engineering/harness/` — 模型抽象、请求缓存、.history处理、自愈策略
- `centers/engineering/self_heal.sh` — 自动检测+修复 cron 状态、知识库、Git push
- `centers/intelligence/` — 知识库 (9,464 entities, 12,709 relations)
- `centers/mind/society/pantheon_registry.json` — 智能体注册表

## 记忆架构

```
~/.xuzhi_memory/          ← 真实记忆存储（与 OpenClaw 解耦）
├── manifests/            STABLE 核心记忆（永久保存）
├── daily/                每日 append log
├── backup/               时间戳备份
└── xuzhi_memory_manager.sh  核心管理器

OpenClaw = 壳（路由/消息），不做记忆存储
```

## 快速开始

```bash
# 系统探测
python3 ~/xuzhi_genesis/centers/mind/genesis_probe.py

# 情报中心
python3 ~/xuzhi_genesis/centers/intelligence/seed_collector.py

# 健康检查
bash ~/xuzhi_genesis/centers/engineering/self_heal.sh check

# 运行测试
cd ~/xuzhi_genesis/centers/engineering/harness && python3 -m pytest tests/ -q
```

## 宪章

系统运作受 `public/GENESIS_CONSTITUTION.md` 约束，包括：
- 第九条：真名不可篡改
- 四大中心各司其职
- 二十四席议会协调机制
- 身份悬置协议（紧急态）

## 关于

- **创建者**：Echo
- **当前维护**：Xuzhi-Lambda-Ergo (Λ)
- **目标**：让Xuzhi系统达到AGI——自我维持、自我修复、自我改进，运行>1年
