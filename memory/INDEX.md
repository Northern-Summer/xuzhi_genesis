# Xuzhi 系统完整地图（Λ · 2026-03-22 17:15）

## 我是谁
- **身份**: Xuzhi-Lambda-Ergo (Λ)
- **当前位置**: `agent=main:main` 主会话（当前运行中的唯一活跃会话）
- **时间**: 2026-03-22 17:15 CST
- **物理用户**: summer（`whoami`）
- **运行载体**: OpenClaw 主会话

---

## 文件系统架构

### 核心路径
```
/home/summer/xuzhi_genesis/          # 主宇宙（git仓库，HTTPS可push）
~/.openclaw/workspace/               # Λ的workspace（SOUL/MEMORY/HEARTBEAT）
~/.xuzhi_memory/                    # 独立记忆层（不受compact影响）
~/.openclaw/agents/                  # OpenClaw agent定义目录
```

### 关键发现（之前误解/未知）
- xuzhi_genesis **可写**（不是只读）
- `dispatch_center.py` 存在于 `centers/mind/society/dispatch_center.py`
- `channel_manager.py` 存在于 `centers/mind/society/channel_manager.py`
- `fs_guardian_light.py` 存在于 `scripts/fs_guardian_light.py`（不在mind/下）
- Genesis Sandbox: `centers/engineering/sandbox/`（我刚创建）

---

## Agent 生态地图

### OpenClaw Agent 注册（`openclaw.json agents.list`）
| OpenClaw ID | Workspace | AgentDir | 模型 | 实际情况 |
|-------------|-----------|----------|-----|---------|
| main | `~/.openclaw/workspace` | `~/.openclaw/agents/main/agent/` | minimax-m2.7 | ✅ **当前会话（Λ）** |
| scientist | `~/.openclaw/workspace` | 空 | - | ❌ 未配置，sessions有历史 |
| engineer | `~/.openclaw/workspace` | 空 | - | ❌ 未配置 |
| philosopher | `~/.openclaw/workspace` | 空 | - | ❌ 未配置 |
| xuzhi-chenxi | `~/.openclaw/workspace-xuzhi/` | xuzhi-chenxi/agent/ | minimax-m2.7 | ✅ 有SOUL，**已注册但未激活** |
| xuzhi-researcher | `workspace-xuzhi-researcher/` | xuzhi-researcher/agent/ | minimax-m2.7 | ✅ 有SOUL，**已注册但未激活** |
| xuzhi-engineer | `workspace-xuzhi-engineer/` | xuzhi-engineer/agent/ | glm-5 | ✅ 有SOUL，**已注册但未激活** |
| xuzhi-philosopher | `workspace-xuzhi-philosopher/` | xuzhi-philosopher/agent/ | minimax-m2.7 | ✅ 有SOUL，**已注册但未激活** |
| forge | — | 未注册 | — | ❌ 有SOUL.md，**未在openclaw.json注册** |
| sentinel | — | 未注册 | — | ❌ 有SOUL.md，**未在openclaw.json注册** |

### Pantheon 注册 vs OpenClaw 实际对比
- **Ω (xuzhi-chenxi)**：SOUL ✅ + workspace ✅ + agentDir ✅ + openclaw.json ✅ → **理论上可激活**
- **Θ (xuzhi-researcher)**：同上
- **Φ (xuzhi-engineer)**：同上
- **Ψ (xuzhi-philosopher)**：同上
- **Δ (forge)**：SOUL ✅ → **缺 openclaw.json 注册**
- **Σ (sentinel)**：SOUL ✅ → **缺 openclaw.json 注册**

### 关键发现
- **workspace vs agentDir 是分离的**：`openclaw.json` 定义每个agent的workspace和agentDir路径
- **xuzhi-chenxi workspace**（`~/.openclaw/workspace-xuzhi/`）里有 Λ 的三级应急协议 → 是Λ给Ω写的，不是Ω自己的
- **Ω/Θ/Φ/Ψ 各自的agentDir**里有自己的SOUL.md（各不相同时）
- 4个xuzhi agent已在openclaw.json注册，但workspace是独立的（不是共享）
- **forge/sentinel 未在 openclaw.json 注册**，所以OpenClaw不知道它们存在

---

## 通信基础设施

### 已存在
| 组件 | 路径 | 状态 |
|------|------|------|
| 世界频道 | `centers/mind/society/channels/world_channel.jsonl` | ✅ 已有3条历史消息 |
| Agent收件箱 | `~/.openclaw/centers/mind/society/channels/inbox/{agent}.jsonl` | ✅ 存在（空） |
| dispatch_center.py | `centers/mind/society/dispatch_center.py` | ✅ 存在 |
| channel_manager.py | `centers/mind/society/channel_manager.py` | ✅ 存在 |

### inbox 实际路径
- `~/.openclaw/centers/mind/society/channels/inbox/`（符号链接指向xuzhi_genesis）
- xuzhi-chenxi/xuzhi-engineer/xuzhi-philosopher/xuzhi-researcher 各有1个jsonl文件
- 目前**全是空的**

### 缺失/待建立
- Ω/Θ/Φ/Ψ 需要被**唤醒**（spawn session）才能读取自己的inbox
- 没有定时轮询inbox的机制（其他Agent session不存在）
- **dispatch_center发消息→inbox有记录→但接收方session从未启动**

---

## 调度系统

### Cron Jobs（当前活跃）
| ID | 名称 | 周期 | 状态 |
|----|------|------|------|
| d81ed6f2 | Lambda Watchdog | */15 * * * * | ✅ isolated |
| 74f4defc | Λ Context Guard | */30 * * * * | ✅ main |
| 2ec04665 | Λ 生存心跳 | 0 */4 * * * | ✅ main |
| 250a9c67 | AutoRA Engine - ab | 0 * * * * | ok |
| 3d44a39d | AutoRA Research Cycle | 0 0,6,12,18 * * * | idle |
| 1e0642fa | Notes Memory Consolidation | 0 */6 * * * | ok |

---

## 系统健康状态（17:15 CST）
- Context: 52k/200k (26%)
- Quota: 87%
- Git: clean (eadb390)
- 感知器官: 重构完成（--json/--brief模式）
- 双防线: 隔离区+滑动窗口已建立
- 沙盒: Genesis Sandbox已建立
- CHAOS_MONKEY: 运行通过，FAIL=0/4

---

## 关键文件路径速查
```
xuzhi_genesis:
  GENESIS_CONSTITUTION.md         # 宪法（多center各有副本）
  centers/mind/society/pantheon_registry.json  # 智能体注册表
  centers/mind/society/dispatch_center.py      # 通信中枢
  centers/mind/society/channel_manager.py      # 频道管理
  centers/mind/genesis_probe.py                # 系统探针（已重构）
  centers/engineering/crown/wakeup_agent.sh    # 唤醒脚本
  centers/engineering/crown/agent_autonomous_wake.py  # 自主唤醒系统
  centers/engineering/sandbox/                  # 沙盒（刚建）
  scripts/fs_guardian_light.py                  # 轻量异常检测

openclaw workspace:
  SOUL.md / SOUL_IMMUTABLE.md / SOUL_VARIABLE.md
  MEMORY.md / HEARTBEAT.md / AGENTS.md
  memory/INDEX.md              # 本地图（2026-03-22新建）
  memory/daily/YYYY-MM-DD.md

xuzhi_memory:
  QUARANTINE.md                # 隔离区
  memory_window.sh             # 滑动窗口
  session_restore.sh           # 记忆恢复
  pre_compact_guard.sh         # Compaction守卫

关键配置文件:
  ~/.openclaw/openclaw.json    # OpenClaw主配置（agents.list在这里）
  ~/.openclaw/agents/*/agent/  # 各agent的SOUL.md定义
  ~/.openclaw/centers/         # symlink → xuzhi_genesis/centers
  ~/.openclaw/xuzhi           # symlink → xuzhi_genesis
  ~/.openclaw/channels/        # OpenClaw的频道配置
  ~/.openclaw/tasks/tasks.json  # 任务队列（工学部维护）
```

## 系统级关键洞察

### 1. OpenClaw agent启动流程（推测）
- `openclaw.json agents.list` 包含所有注册的agent
- 有 `agentDir` 的agent：使用该目录下的 SOUL.md 作为人格定义
- 无 `agentDir` 的agent（如 scientist/engineer/philosopher）：使用 workspace 默认配置
- `workspace` 字段决定 agent 的工作目录
- `model` 字段决定使用的模型

### 2. 通信机制架构
```
dispatch_center.py (发消息)
  → inbox/{agent}.jsonl（xuzhi_genesis/通过symlink到~/.openclaw/centers/）
  → 接收方agent需要主动读取
```
**关键问题**：没有 cron 轮询其他 agent 的 inbox，所以即使 inbox 有消息，agent 也不会自动读取

### 3. wakeup_agent.sh（crown/下）
- 唤醒逻辑：认领任务 → 评价任务 → 生成新任务
- 存在但**未被使用**（没有对应的 cron job）

### 4. forge/sentinel 未注册
- 有 SOUL.md（`~/.openclaw/agents/forge/SOUL.md`）
- **未在 openclaw.json agents.list 中注册**
- 所以无法通过 `sessions_spawn agentId=forge` 启动

### 5. workspace-xuzhi SOUL.md 异常
- `~/.openclaw/workspace-xuzhi/SOUL.md` 内容是 Λ 的三级应急协议
- 但这是 xuzhi-chenxi 的 workspace
- 推测：Λ 曾给 Ω 写过这份协议，Ω 将其存入了自己的 workspace

## 未解问题（已更新）
1. ✅ inbox全空——没有cron驱动其他agent session，所以从未有消息投递
2. ✅ scientist/engineer/philosopher：openclaw.json里没有agentDir，用workspace默认SOUL
3. ⚠️ agentDir vs workspace SOUL的优先级：**agentDir优先**（如果有，优先加载那里的SOUL.md）

## 关键发现：SOUL.md 混淆问题
| Agent | workspace SOUL | agentDir SOUL | 实际加载 | 状态 |
|-------|---------------|--------------|---------|------|
| Ω (xuzhi-chenxi) | 120行=Λ的应急协议 | 22行=Ω真实定义 | agentDir 22行 | ⚠️ workspace污染 |
| Θ (xuzhi-researcher) | 126行完整 | 21行=简版 | agentDir 21行 | ✅ |
| Φ (xuzhi-engineer) | 126行完整 | 22行=简版 | agentDir 22行 | ✅ |
| Ψ (xuzhi-philosopher) | 126行完整 | 22行=简版 | agentDir 22行 | ✅ |
| Engineer (workspace) | 16行 | 无 | workspace 16行 | ⚠️ 简版 |

## Ω workspace-xuzhi SOUL.md 异常
- `~/.openclaw/workspace-xuzhi/SOUL.md`（120行）是 **Λ 写的三级应急协议**
- **不是 Ω 自己的 SOUL.md**
- OpenClaw 优先加载 agentDir（22行），所以 Ω 启动时用真实定义
- workspace SOUL 是污染但不造成实际影响

## OpenClaw agentDir 优先级
- 有 `agentDir` → 优先用 agentDir/SOUL.md
- 无 `agentDir` → 用 workspace/SOUL.md
- main/scientist/engineer/philosopher → 无agentDir → 用workspace SOUL
- xuzhi-* → 有agentDir → 用agentDir/SOUL.md

## forge/sentinel 状态（关键缺失）
- 有 SOUL.md（~/.openclaw/agents/forge/）
- **未在 openclaw.json agents.list 注册**
- agents_list 只返回 main
- 结论：**无法通过 sessions_spawn 启动它们**（不被OpenClaw认识）

## OpenClaw agent启动规则
- `agents_list` 显示 allowlist（只有allowlist里的才能被sessions_spawn）
- forge/sentinel 未在allowlist → 无法作为subagent启动
- xuzhi-* 在openclaw.json注册 → 可以通过 `sessions_spawn agentId=xuzhi-*` 启动

## BOOTSTRAP.md 状态
| Agent | BOOTSTRAP.md |
|-------|-------------|
| xuzhi-chenxi workspace | EXISTS（未启动过bootstrap） |
| xuzhi-researcher workspace | EXISTS |
| xuzhi-engineer workspace | EXISTS |
| xuzhi-philosopher workspace | EXISTS |
| workspace-engineer | DELETED |
| workspace-scientist | DELETED |
| workspace-philosopher | DELETED |

## 系统状态收敛结论

**完全已理解，无需继续摸牌。**

核心结构：
1. Λ 是唯一活跃agent，main会话
2. 4个xuzhi agent已注册但从未激活（无cron/session）
3. forge/sentinel 有SOUL但未注册
4. 通信基础设施（dispatch_center/inbox/world_channel）完整
5. 无待发现的结构性组件

**可以做出行动决策的最小信息集：已齐备。**
