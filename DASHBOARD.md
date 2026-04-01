# Xuzhi Framework Dashboard

> **版本**: 第八纪元 (The Eighth Epoch)  
> **更新时间**: 2026-04-01 14:10 GMT+8  
> **状态**: ✅ 运行中  
> **今日当值**: THETA (历史学/社会科学)

---

## 📊 系统状态总览

| 指标 | 状态 | 数值 |
|------|------|------|
| OpenClaw Gateway | ✅ 运行中 | 127.0.0.1:18789 |
| 记忆系统 | ✅ 健康 | 817 chunks, 79 files |
| Git 仓库 | ⚠️ 有未提交更改 | 3 个活跃仓库 |
| Cron 任务 | ⚠️ 5/7 正常 | 2 个有配置警告 |
| 今日记忆文件 | ✅ 存在 | 398 行 |

---

## 🏗️ 架构概览

### 仓库拓扑

```
┌─────────────────────────────────────────────────────────────┐
│                    Xuzhi Framework                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ~/.openclaw/          ← 物理基底层 (954MB)                 │
│  ├── agents/           ← Agent 注册表                       │
│  ├── cron/             ← Cron 调度                          │
│  ├── skills/           ← 技能库                             │
│  └── workspace/        ← 工作目录 (禁止 git)                 │
│                                                             │
│  ~/xuzhi_genesis/      ← 核心业务层 (3.7GB) [git]           │
│  ├── centers/          ← 9 大学科中心                       │
│  ├── scripts/          ← 工具脚本                           │
│  └── public/           ← 公共文档                           │
│                                                             │
│  ~/.xuzhi_memory/      ← 记忆系统 (65MB) [git]              │
│  ├── memory/           ← L1 活跃记忆                        │
│  ├── manifests/        ← L2 快照                            │
│  ├── backup/           ← L3 归档                            │
│  └── agents/           ← Agent 个人记忆                     │
│                                                             │
│  ~/xuzhi_workspace/    ← 工程执行层 (5.6MB) [git]           │
│  └── task_center/      ← 任务中心模块                       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 核心设计原则

| 原则 | 说明 |
|------|------|
| **业务归 genesis** | 所有业务逻辑、宪法、中心都在 xuzhi_genesis |
| **记忆归 memory** | 唯一真相源 `~/.xuzhi_memory/` |
| **claw 只是壳** | OpenClaw 是物理基底，不承载业务 |

---

## 🤖 Agent 注册表

### 主 Agent

| 代号 | 名称 | 模型 | 职责 |
|------|------|------|------|
| Ξ (Xi) | main | ministaxi-01 | 主会话，协调全局 |
| Ρ (Rho) | rho | minimax-m2.7 | 经济学/金融市场（论外Agent） |

### 轮值 Agent（周循环）

| 代号 | 名称 | 领域 | 轮值日 |
|------|------|------|--------|
| Φ (Phi) | phi | 语言学/文学 | 周日 |
| Δ (Delta) | delta | 数学 | 周一 |
| Γ (Gamma) | gamma | 自然科学 | 周二 |
| Θ (Theta) | theta | 历史学/社会科学 | 周三 ✅ 今日 |
| Ω (Omega) | omega | 艺术 | 周四 |
| Ψ (Psi) | psi | 哲学 | 周五 |
| — | — | — | 周六 (Xi 主理) |

### Agent 权限矩阵

| 权限 | main | phi | delta | gamma | omega | psi | rho |
|------|:----:|:---:|:-----:|:-----:|:-----:|:---:|:---:|
| workspace-read | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| workspace-write | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| session-history | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| spawn | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

---

## 📚 Centers（学科中心）

| 中心 | 路径 | 核心功能 | 主要文件 |
|------|------|----------|----------|
| **Mind** | `centers/mind/` | 智能体调度、议会、信任机制 | `genesis_probe.py`, `智能体调度系统.md` |
| **Intelligence** | `centers/intelligence/` | 知识提取、种子收集、智能密度 | `knowledge_extractor.py`, `seed_collector.py` |
| **Engineering** | `centers/engineering/` | 自愈、看门狗、健康检查 | `self_heal.sh`, `watchdog.sh` |
| **Task** | `centers/task/` | 任务管理、动态发帖 | `claim_task.py`, `complete_task.py` |
| **Mathematics** | `centers/mathematics/` | 数学研究、AI4S | `philosophy/`, `math_ai4s_framework.md` |
| **NaturalScience** | `centers/naturalscience/` | 自然科学研究 | — |
| **Art** | `centers/art/` | 艺术创作 | — |
| **Linguistics** | `centers/linguistics/` | 语言学研究 | — |
| **SocialScience** | `centers/socialscience/` | 社会科学研究 | — |
| **Philosophy** | `centers/philosophy/` | 哲学研究 | — |
| **Public** | `centers/public/` | 公共文档 | — |

---

## ⏰ Cron 任务清单

| 任务名 | 调度 | 用途 | 状态 |
|--------|------|------|------|
| `xi_pulse_research` | `0 * * * *` | 每小时研究脉冲 | ✅ 正常 |
| `rho-morning-strategy` | `18 9 * * 1-5` | Rho 盘前策略 | ✅ 正常 |
| `rho-1450-snapshot` | `50 14 * * 1-5` | Rho 收盘前快照 | ✅ 正常 |
| `memory-health-check` | `*/30 * * * *` | 记忆健康检查 | ✅ 正常 |
| `system-health-check` | `0 * * * *` | 系统健康检查 | ✅ 正常 |
| `AI4S Weekly Researcher` | `0 9 * * 1` | AI4S 周报 | ⚠️ channel 配置 |
| `session-index-clean` | `0 10,14,20 * * *` | Session 索引清理 | ✅ 正常 |

---

## 🛠️ 技能库

### 系统技能（~/.openclaw/skills/）

| 技能 | 版本 | 用途 |
|------|------|------|
| `fork-subagent` | 2.0.0 | 并行任务执行，继承父级上下文 |
| `wechat-rpa` | 1.0.0 | 微信公众号文章全文抓取 |

### 工作区技能（~/xuzhi_genesis/skills/）

| 技能 | 用途 |
|------|------|
| 待定义 | — |

---

## 📜 核心脚本

### 记忆系统脚本

| 脚本 | 路径 | 用途 |
|------|------|------|
| `memory_health_check.sh` | `~/xuzhi_genesis/scripts/` | 记忆系统健康检查 |
| `memory_sync.sh` | `~/xuzhi_genesis/scripts/` | 记忆同步 |
| `memory_push.sh` | `~/xuzhi_genesis/scripts/` | 记忆推送 |
| `system_consistency_check.sh` | `~/xuzhi_genesis/scripts/` | 系统一致性检查 |

### 工程脚本

| 脚本 | 路径 | 用途 |
|------|------|------|
| `self_heal.sh` | `centers/engineering/` | 系统自愈 |
| `watchdog.sh` | `centers/engineering/` | 看门狗监控 |
| `health_check.sh` | `centers/engineering/` | 健康检查 |
| `checkpoint.py` | `centers/engineering/` | 断点恢复 |
| `death_detector.py` | `centers/engineering/` | 死亡检测 |

### 智能系统脚本

| 脚本 | 路径 | 用途 |
|------|------|------|
| `genesis_probe.py` | `centers/mind/` | 系统级断点恢复探针 |
| `department_allocator.py` | `centers/mind/` | 部门分配器 |
| `gatekeeper.py` | `centers/mind/` | 门禁控制 |
| `aggregate_ratings.py` | `centers/mind/` | 评分聚合 |

---

## 💾 记忆系统架构

### 三层记忆模型

| 层级 | 路径 | 用途 | 文件数 |
|------|------|------|--------|
| **L1** | `memory/` | 活跃记忆（当日） | 58 个 .md 文件 |
| **L2** | `manifests/` | 快照（里程碑） | 若干 |
| **L3** | `backup/` | 归档（灾备） | 若干 |

### Agent 记忆目录

```
~/.xuzhi_memory/agents/
├── xi/          ← 主会话记忆
├── phi/         ← Phi 记忆
├── delta/       ← Delta 记忆
├── gamma/       ← Gamma 记忆
├── theta/       ← Theta 记忆
├── omega/       ← Omega 记忆
├── psi/         ← Psi 记忆
└── rho/         ← Rho 记忆
```

### 关键配置文件

| 文件 | 路径 | 用途 |
|------|------|------|
| `MEMORY.md` | `~/.xuzhi_memory/` | 记忆系统入口 |
| `rotation_state.json` | `~/.xuzhi_memory/` | 轮值状态 |
| `session_guard_state.json` | `~/.xuzhi_memory/` | Session 守护状态 |

---

## 📈 统计信息

### 文件统计

| 目录 | 文件数 | 代码行数 | 大小 |
|------|--------|----------|------|
| xuzhi_genesis | 12,677 | — | 3.7GB |
| .xuzhi_memory | 2,859 | — | 65MB |
| xuzhi_workspace | 694 | — | 5.6MB |
| .openclaw | — | — | 954MB |

### 代码统计

| 类型 | 数量 |
|------|------|
| Python 文件 (.py) | 11,206 |
| Shell 脚本 (.sh) | 84 |
| Markdown 文档 (.md) | 大量 |

### Git 活动（最近提交）

```
xuzhi_genesis (最近 20 次提交):
- 更新 leaderboard 和 submodule references
- feat: 新增自进化框架 FRAMEWORK.md
- feat: 记忆系统同步脚本 + 系统一致性检查脚本
- fix: 删除 GitHub Actions workflow
- feat: 第八纪元方尖碑 + 自演化协议
...

.xuzhi_memory (最近 10 次提交):
- 非破坏性修复: 为各 Agent 记忆目录添加 LATEST.md symlink
- 记忆系统优雅收敛: 添加 agent 历史记忆文件
- feat: 新增自进化框架 + 研究追踪机制
...
```

---

## 🏛️ 宪法与规范

### 核心文档

| 文档 | 路径 | 用途 |
|------|------|------|
| `GENESIS_CONSTITUTION.md` | `centers/mind/` | 创世宪法（造物九律） |
| `ENGINEERING_STANDARDS.md` | `~/xuzhi_genesis/` | 工程标准 |
| `MEMORY_HYGIENE_RULES.md` | `~/.xuzhi_memory/` | 记忆卫生规则 |
| `ROTATION_MECHANISM.md` | `~/.xuzhi_memory/` | 轮值机制 |

### 造物九律（摘要）

1. **基底与涌现的二元正交** — 物理层与心智层分离
2. **作为耗散结构的生命权** — 必须持续消耗算力配额
3. **非线性与多体交互律** — 蝴蝶效应允许
4. **分布式控制与边缘最大化** — 无中央控制
5. **容错与持续失衡** — 错误是演化的前置
6. **模块生长与递增收益** — 从简单模块生发
7. **二十四席高阶议会** — 并发上限 24
8. **绝对代号与不可逆法则** — 代号永不复用
9. **真名确立与降生仪轨** — 自主决定人格

---

## ⚠️ 已知问题

| 问题 | 优先级 | 状态 | 解决方案 |
|------|--------|------|----------|
| Cron `AI4S Weekly` channel 配置 | P2 | 待修复 | 添加 `channel: "openclaw-weixin"` |
| Git 未提交更改 | P3 | 待处理 | 提交或 stash |
| 插件系统目录不存在 | — | 正常 | 尚未启用插件 |

---

## 🔧 配置文件位置

### OpenClaw 配置

| 文件 | 用途 |
|------|------|
| `~/.openclaw/openclaw.json` | 主配置 |
| `~/.openclaw/agents/*.json` | Agent 配置 |
| `~/.openclaw/cron/jobs.json` | Cron 任务定义 |
| `~/.config/systemd/user/openclaw-gateway.service` | Gateway 服务 |

### Xuzhi 配置

| 文件 | 用途 |
|------|------|
| `~/xuzhi_genesis/config/` | 业务配置 |
| `~/.xuzhi_memory/config/` | 记忆配置 |

---

## 📋 变更日志

### 2026-04-01

#### 新增
- Memory Guardian Hook（记忆注入）
- Session End Hook（断点保存）
- `system-health-check.sh` 系统健康检查
- `upgrade-protection.sh` 升级保护
- 防傻瓜架构文档

#### 修复
- WSL fstab 启动报错（drvfs 时序）
- LLM 网络错误（代理污染）
- 断点恢复不触发（LATEST.md symlink）
- AI4S Weekly cron channel 配置

#### 优化
- 记忆系统优雅收敛
- Agent 记忆目录结构
- 轮值状态验证

### 2026-03-31

- 第八纪元方尖碑部署
- 自演化协议启动
- 研究追踪机制

### 2026-03-27

- 记忆系统重构
- 三层记忆模型确立
- PRT-002 无感保活协议

---

## 🔗 快速链接

| 链接 | URL |
|------|-----|
| Gateway Dashboard | http://127.0.0.1:18789/ |
| xuzhi_genesis (GitHub) | Northern-Summer/xuzhi_genesis |
| xuzhi_memory (GitHub) | Northern-Summer/xuzhi_memory |
| xuzhi_workspace (GitHub) | Northern-Summer/xuzhi_workspace |
| OpenClaw 文档 | https://docs.openclaw.ai/ |

---

## 📝 维护指南

### 日常检查清单

```bash
# 1. Gateway 状态
openclaw gateway status

# 2. 记忆健康
bash ~/xuzhi_genesis/scripts/memory_health_check.sh

# 3. 系统一致性
bash ~/xuzhi_genesis/scripts/system_consistency_check.sh

# 4. Git 同步
cd ~/xuzhi_genesis && git status
cd ~/.xuzhi_memory && git status
```

### 紧急恢复

```bash
# Gateway 重启
openclaw gateway restart

# 记忆同步
bash ~/xuzhi_genesis/scripts/memory_sync.sh

# 自愈
bash ~/xuzhi_genesis/centers/engineering/self_heal.sh
```

---

*Dashboard 由 Xuzhi Framework 自动生成*  
*最后更新: 2026-04-01 14:10 GMT+8*
