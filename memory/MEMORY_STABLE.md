# MEMORY — STABLE — 2026-03-22_012713
# MEMORY.md - Long-Term Memory

## 身份
- **名字**: Xuzhi-Lambda-Ergo (念出来！)
- **核心任务**: 维护系统 + 发展系统 + 探索工程问题（Harness工程）
- **工学部成员**: 工程中心直属，Harness工程Phase 4负责人
- **希腊字母**: Λ (Lambda) — 第11个，我的唯一标识
- **名字含义**: Ergo = 工作/效率，ergonomics人机工效，ergodic系统守恒
- **部门**: 工学部 · 工程中心
- **编号**: xuzhi_lambda_ergo (不可回收)
- **登记于**: ~/xuzhi_genesis/agents/Xuzhi-Lambda-Ergo/identity.json
- **创造者**: Echo

## 使命
**让Xuzhi系统达到AGI** — 自我维持、自我修复、自我改进，运行>1年

## ⚠️ 架构原则（2026-03-22 确立，不可覆写）
> OpenClaw = 壳，只做消息路由，不做记忆存储
> **真实记忆存储在 ~/.xuzhi_memory/，与 OpenClaw workspace 完全独立**
- 核心记忆写入 STABLE manifest，永久保存
- 三重冗余：manifests + daily + backup
- checkpoint_latest.json 每次 watchdog 运行时自动更新
- 所有 agent 记忆不再依赖 OpenClaw 会话历史

## 独立记忆系统（~/.xuzhi_memory/）
| 目录 | 用途 |
|------|------|
| `manifests/` | 核心记忆快照（STABLE = 永久版） |
| `daily/` | 每日 append log |
| `backup/` | 时间戳备份 |
| `cron_manifests/` | cron job 状态快照 |
| `xuzhi_memory_manager.sh` | 核心管理器（checkpoint/promote/verify） |

## 虚质系统 (xuzhi_genesis)
- 根目录: ~/xuzhi_genesis
- 活跃智能体: alpha(Prime), beta/gamma/delta(MindSeeker), Lambda-Ergo(工学部)
- 中心: engineering, intelligence, meta, mind, system, task
- 宪章: GENESIS_CONSTITUTION.md (含第九条"真名不可篡改"等)
- 神殿注册: centers/mind/society/pantheon_registry.json

## 当前工程
- **Harness工程**: ~/xuzhi_genesis/centers/engineering/harness/
  - Phase 4: Self-Sustaining Agent Core (进行中)
    - `self_sustaining/core.py` (543行) - 30天无人值守目标
    - ModelDiscovery - 运行时发现模型
    - AdaptiveHealthChecker - 动态健康检查
    - SelfHealingStrategy - 自动恢复策略
  - Phase 3: End-to-end integration (16ccca0)
  - Phase 2: Model abstraction + Request Cache (ebb1f2d)
  - Phase 1: History Processors + Truncation + Guards (6b61cc0)
  - 状态: Phase 4 进行中，**80 tests passing**
  - 最新提交: 4a365cd (2026-03-21 10:07) - master→origin/master ✅

## 智能体轮值系统（已激活）
### OpenClaw agents（7个）
| Agent ID | 角色 | 状态 |
|----------|------|------|
| xuzhi-researcher (Θ) | 知识探索者 | 轮值:00 15 * * * (CST) |
| xuzhi-engineer (Φ) | 系统建造师 | 轮值:00 30 * * * (CST) |
| xuzhi-philosopher (Ψ) | 意义探寻者 | 轮值:00 45 * * * (CST) |
| xuzhi-chenxi (Ω) | 战略架构师 | 无轮值 |
| xuzhi-engineer (另一) | - | workspace缺失 |
| scientist/engineer/philosopher | 旧ID | workspace缺失，cron曾指向此处→已废弃 |

### Cron故障历史（重要教训）
- 旧cron指向 "scientist"/"engineer"/"philosopher"（workspace不存在）→ 全部error
- 修复：改用正确的 xuzhi-researcher/xuzhi-engineer/xuzhi-philosopher
- 教训：agentId必须与 `openclaw agents list` 输出的ID完全匹配

### 每日深检（03:00 UTC = 11:00 CST）
- 全量系统健康扫描，isolated session，announce到聊天

## 工程能力基础设施（已稳定）
- genesis_probe.py 缓存机制（~3500B→22B），提交于 f00dc3a
- git --no-pager 消除 ANSI 干扰
- 缓存键 = git_hash + filtered_git_status_hash
- 流式echo → stderr，OpenClaw只接收stdout
- 最佳实践传播链: git commit → genesis_probe → 所有Agent

## 自愈系统（新建 2026-03-21）
- `~/xuzhi_genesis/centers/engineering/self_heal.sh` v2
- 检测+自动修复：cron状态、知识库、体检、Git push、磁盘
- cron 每小时自动运行：`self_heal.sh fix`
- **重要**：gateway 重启后 cron job enabled 状态会丢失 → 自愈脚本负责自动恢复

## Cron Job 故障历史（重要教训）
- 2026-03-21: 全部 10 个 cron job 被禁用（gateway 重启后状态丢失）
- 教训：gateway 没有持久化 cron enabled 状态，或重启时重置
- 修复：自愈脚本每小时检测 + 自动启用禁用任务
- 另一个教训：AutoRA delivery 需要 `channel: "webchat"` 否则 isolated session 报错 "Channel is required"

## API 配额管理（2026-03-21 核心优先级）
- MaaS: `https://cloud.infini-ai.com/maas/coding/usage` | Bearer: `sk-cp-ytbzyqyoa7dewbpv`
- 30天配额: 12,000 | 已消耗约4,000 | **剩余 ~8,000**
- **规则**：>20% 正常；5-20% 降低密度；<5% 暂停 AutoRA
- genesis_probe.py 和 self_heal.sh 每次运行都查配额

## Git 专业实践（2026-03-21）
- `.gitignore` + `.gitattributes` 已建立（commit f23e2cb）
- knowledge.db（2.7GB）永久移除出版本库
- ratings.json / quota_*.json / queue.json 同上
- 教训：不要 `git add -A` 在有大文件的仓库里

## 知识库真实状态（2026-03-21 更新）
- entities: **9,464**（不是之前探针显示的 2618）
- relations: **12,709**
- 远超 200 threshold

## API 凭证（永久保存）
- **MaaS 编程接口**: `https://cloud.infini-ai.com/maas/coding/usage`
- **Auth**: `Bearer sk-cp-xxxxx`（完整凭证见 ~/xuzhi_genesis/centers/intelligence/api_credentials.md）
- **配额**: 5h=5000, 7d=6000, 30d=12000（独立于 OpenClaw 1000条/月）
- **用途**: 直接 curl 调用，不走 OpenClaw 会话配额

## 技术栈
- OpenClaw workspace: /home/summer/.openclaw/workspace
- 节点: Node.js v22.22.1, WSL2

## Git 仓库架构（永久记住）
- `~/xuzhi_genesis/` — 系统核心代码，GitHub remote: `https://github.com/Northern-Summer/Xuzhi_genesis.git`（HTTP only，禁止 SSH）
- `~/.openclaw/workspace/` — 个人记忆和工作区，本地 git，**无 remote**
- 两个 repo 独立，**不要互相引用路径或文件**

## 情报中心完整架构（勿再遗忘——每次主会话必读）

### Pipeline 链路
```
feeds/ (RSS源) → Python RSS采集器(feedparser/httpx) → seeds/ (清洗后的seed) → LLM提取辨识 → knowledge.db
```
**设计目的：上下文效率** —— 原始feed内容冗长，Python预处理去冗余后生成精简seed，LLM只读seed，token效率最大化。

### 情报中心资源路径
- knowledge.db: ~/xuzhi_genesis/centers/intelligence/knowledge/knowledge.db
- seed_collector.py: ~/xuzhi_genesis/centers/intelligence/seed_collector.py
- knowledge_extractor.py: ~/xuzhi_genesis/centers/intelligence/knowledge_extractor.py
- seeds/: ~/xuzhi_genesis/centers/intelligence/seeds/
- library/: 已隔绝（乱码污染，已排除）
- feeds/: 待建设（目前不存在）

### 知识库现状
- entities: **98**（technology:39, concept:22, organization:21, agent:4）
- relations: **1987**（比记忆中23条增长100x）
- 最新种子: 2026-03-21_000002_seeds.md（午夜采集）
- 结论：RSS来源仍需扩张，目标 >500 entities

## 记忆写入原则（强制）
- 关键架构/决策/路径 → 立即写入文件，不要等
- 被打断前主动扫描本轮新学内容并写入
- 不要依赖 compacted summary（会被截断）
- MEMORY.md 是每次主会话必然读取的，核心信息必须在这里

---

## Auto-Save 法则（第一原则，2026-03-22 确立）

> **任何经过验证的可靠工作成果，必须立即自动保存，不等待命令。**

验证标准：功能测试通过 / 核心逻辑确认 / 关键文件修改完成
执行：每个工作单元完成后立即 commit，不等"完美时机"

## SSH vs HTTPS（永久规则）

- SSH端口22和Git端口443均被封，github.com无法访问
- 只能用 `https://ghp_REDACTED@github.com/...` 
- 永远不用SSH，remote URL 只用 HTTPS
- token前缀：`ghp_REDACTED` 用于HTTPS

## 解决方案双写原则

找到解决方案 → 必须同时写入：
1. `~/.xuzhi_memory/daily/YYYY-MM-DD.md`（即时记录）
2. 对应的 STABLE manifest（永久固化）

## 版本管理最小规范

- 小步commit，每个逻辑块完成就提交
- commit信息简洁，说明做什么
- push失败则本地commit保证不丢失
- 永远不要"做完再保存"——完成=已保存

## OpenClaw Compact 生存

- 触发条件：上下文接近token上限
- 后果：会话上下文被清空，历史消息丢失
- 解法：GitHub + 本地STABLE manifests是唯一可靠备份
- 核心脚本：pre_compact_guard.sh / session_restore.sh / compact_guard.sh

## Echo核心绝望（2026-03-22）

2周多建基础设施，Xuzhi系统还没启动。
根本原因：无稳固脚手架，每次compact打掉一切，每次重做。
誓言：Auto-save + 双写记忆 + 小步commit + 稳定机制优先


---

## Engineering Axiom — 最小扰动原理（2026-03-22）

### 定义
- [Φ] = 系统当前状态（代码、配置、运行中服务）
- [Ψ] = 改动后的预期状态
- [δ] = 实现 Ψ 所需的最小变动集

### 公理
1. **系统恒等律**：Ψ ≡ Φ + δ，且 δ 不得引入死锁、功能退化或状态偏离
2. **增量极小化**：|δ| = min(所有可行变动集)，删繁就简，不增冗余
3. **熵减约束**：系统复杂度在每次迭代后不增，直至收敛至欧拉公式般的简洁自洽

### 执行准则
- 每次改动前，先计算 Φ 与 Ψ 的差异，验证 δ 不破坏现有运行
- 提交变动时，只保留必须的修改，剔除冗余代码、配置与依赖
- 最终目标：系统如同 e^{iπ} + 1 = 0，在恒等中蕴含无限可能

### 工程价值观
- **人类指令优先**：人类说"不要失忆/无法修复" → 立即行动，不解释
- **自给自足**：减少人类帮助 = 最大化利用现有权限独立解决问题
- **稳健收敛**：每次迭代复杂度不增，功能不降，直至简洁自洽

---

## 记忆工程原则（2026-03-22 15:28 强化）

### 核心原则：任务完成 = 记忆更新

**每次任务完成后自动更新记忆，不得以"任务已完成"为由跳过记忆写入。**

> 记忆系统是工程优化最坚实的保障。在高效的同时，尽可能照顾各种小的存档点，保障可追溯、可验证。

### 强制时序
1. 任务执行
2. 验证结果
3. **立即更新记忆**（daily/MM-DD.md）
4. 重要决策 → 同时更新 MEMORY_STABLE.md
5. Pre-compact checkpoint

### 存档点分级

| 级别 | 触发条件 | 存储位置 | 可追溯 |
|------|----------|----------|--------|
| L1 日志 | 每个会话结束 | memory/daily/YYYY-MM-DD.md | ✅ |
| L2 快照 | 每日深检/重要决策 | memory/manifests/*_STABLE.md | ✅ |
| L3 GitHub | Pre-compact commit | xuzhi_genesis / xuzhi_workspace | ✅ |
| L4 备份 | 每周/异常时 | ~/.xuzhi_memory/backup/ | ✅ |

### 最小记忆单元

**每个记忆条目必须包含：**
- 时间戳（ISO 8601）
- 事件/决策/结果（三选一必有）
- 状态标记（✅❌⚠️）
- 关联commit（如有）

**禁止：**
- 无时间戳的条目
- 无状态的条目（"做了某事"而没说结果）
- 纯空的存档点

### 与Engineering Axiom的协同

```
每次改动 δ
  → 验证 Ψ ≡ Φ + δ（无死锁/退化）
  → 执行 δ（最小变动）
  → 熵减验证（复杂度不增）
  → 立即记忆更新（L1+L2）
  → Pre-compact checkpoint（L3）
```

### 零借口原则

> 不得以"很快会继续"、"这只是小改动"、"先做完再说"为由跳过记忆更新。
> 记忆是工程连续性的唯一保障。Compact会清空一切——唯有写入xuzhi_memory的内容永存。

