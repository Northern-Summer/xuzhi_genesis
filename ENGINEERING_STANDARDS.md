# Xuzhi Genesis — 工程规范

> **目的**：固化开发流程，防止临时方案互相干扰，建立业界标准级的工程纪律。
> **适用范围**：所有 xuzhi_genesis 贡献者（人 + Agent）

---

## 1. Git 工作流

### 1.1 黄金法则
```
禁止 git add -A
禁止 git commit -m "fix stuff"
禁止 git push --force
```

### 1.2 Commit 规范
```
<中心> <文件或模块> <一句话描述>

示例：
engineering harness model_discovery.py 添加动态模型发现
intelligence seed_collector.py 修复RSS解析超时bug
mind society/pantheon_registry.json 注册新Agent Eta
```
- 每条 commit 聚焦一件事
- 先 `git diff --cached` 确认后再 commit

### 1.3 文件禁止直接提交
```bash
# pre-commit hook 强制检查
knowledge.db        # 2.7GB，无法合并
*.log               # 本地临时
gateway.log
queue.json          # 运行时状态
ratings.json
quota_*.json
credentials*.json   # 密钥
```

### 1.4 Branch 策略
```
master      — 生产稳定版，只接收经过 CI 的 PR
develop     — 下一版本开发分支
hotfix/*    — 紧急修复
feature/*   — 新功能（从 develop 分出）
```

---

## 2. CI/CD — 每次 Push 自动触发

### 2.1 GitHub Actions Pipeline（.github/workflows/ci.yml）
每个 job 失败 → push 被阻断 → 通知发到前台

**Stage 1: Genesis Probe**
- `genesis_probe.py` 健康检查
- 退出码非0 → CI 失败

**Stage 2: Harness Tests**
- `cd centers/engineering/harness && python3 -m pytest tests/ -q`
- 80+ tests 必须全部通过

**Stage 3: Knowledge Integrity**
- entities > 1000
- relations > 1000
- 无新增 corrupted seed

**Stage 4: Self-Heal Verify**
- `self_heal.sh check` 通过

**Stage 5: Memory Sync**
- 本地 manifest 和 GitHub 同步验证
- `xuzhi_memory_manager.sh verify`

### 2.2 发布规范
```
版本号: <major>.<feature>.<fix>
major — 架构级变更（四大中心重组）
feature — 新功能（情报中心 pipeline、新的Agent）
fix — bug修复

tag 格式: v<version>
CHANGELOG.md 必须更新
```

---

## 3. Self-Heal 自动修复

### 3.1 故障检测清单
| 故障类型 | 检测方式 | 修复动作 |
|---------|---------|---------|
| cron 禁用 | `openclaw cron list` + `jq '.jobs[] | select(.enabled==false)'` | 自动 re-enable |
| Gateway 宕机 | HTTP 200 检查 | 发送 alert |
| Git push 失败 | `git status` + remote 对比 | 重试 push |
| 测试失败 | pytest exit code | revert 最近 commit |
| 知识库损坏 | sqlite integrity_check | 触发 RSS 重新采集 |
| 磁盘不足 | `df -h` | alert + 暂停非核心任务 |
| Agent 消失 | `genesis_probe.py` 无响应 | 触发重建仪轨 |

### 3.2 自愈优先级
```
P0 — cron 禁用（影响所有后续调度）
P1 — Gateway 宕机（系统失联）
P2 — Git push 失败（开发产物丢失）
P3 — 测试失败（质量防线）
P4 — 知识库损坏（上下文退化）
```

---

## 4. Agent 开发规范

### 4.1 新增 Agent 流程
```
1. 在 mind/society/pantheon_registry.json 登记（真名、希腊字母、部门、职责）
2. 编写 SOUL.md（人格定义）
3. 通过 Mind 中心评审
4. 议会投票（>60%同意）
5. 方可注册到 OpenClaw
```

### 4.2 Cron 申请规范
```
申请前必须回答：
- 这次 cron 消耗多少 token/天？
- 价值是否大于等于 100 次后续 API 调用？
- 如果失败，后果是什么？

频率上限：任何 cron 每日 ≤2 次
```

### 4.3 禁止事项
- 禁止用 cron 直接调用 agentTurn（每次都是完整 agent 推理）
- 禁止 cron 在 agentTurn 里套娃 cron
- 禁止修改其他 Agent 的 SOUL.md

---

## 5. 内存与记忆规范

### 5.1 真实记忆存储
```
~/.xuzhi_memory/          ← 唯一真相源（与 OpenClaw 解耦）
├── manifests/STABLE_*    ← 永久核心记忆
├── daily/YYYY-MM-DD.md   ← 每日 append log
└── backup/               ← 时间戳备份

OpenClaw workspace = 工作区，不是记忆区
```

### 5.2 写入原则
- 关键架构决策 → 立即写入 manifest
- 被打断前 → 主动扫描本轮内容并写入
- 不要依赖 compacted summary
- 每次 compact 前 → pre_compact_guard.sh

### 5.3 同步原则
- 所有 local commits 必须在 24h 内 push 到 GitHub
- 每次 push 前 .gitignore 必须更新（如有新增临时文件）
- push 验证：`git remote -v` + `git log origin/..HEAD`

---

## 6. 工程会议纪则

> **每次重要开发前**，对照本规范检查：
> - [ ] 这次改动涉及哪些文件？
> - [ ] 会破坏现有测试吗？
> - [ ] 需要新增 cron 或 agent 吗？
> - [ ] commit message 符合规范吗？
> - [ ] 准备好 CHANGELOG 了吗？

---

*本规范由 Λ (Xuzhi-Lambda-Ergo) 编写于 2026-03-22*
*经 Echo 确认后生效*

---

## 7. 动态/静态分离原则（PRT-002）

### 7.1 原则
所有「动态内容」（日志、缓存、历史数据、种子）必须写入 `~/.xuzhi_memory/`（可写层），禁止写入 `~/xuzhi_genesis/`（只读层）。

### 7.2 分类标准

| 类型 | 定义 | 写入位置 |
|------|------|---------|
| **动态** | 会随时间增长的文件：日志、缓存、临时数据、历史种子 | `~/.xuzhi_memory/` |
| **静态** | 源码、脚本、配置、宪章、公共协议 | `~/xuzhi_genesis/centers/` |

### 7.3 实施规则
- **新建文件前先问**：「这个会随时间增长吗？」
  - 是 → 写入 `~/.xuzhi_memory/`
  - 否 → 写入 `~/xuzhi_genesis/centers/`（只读）
- **已有动态内容**：通过 `memory_window.sh` 定期从只读分区迁移到可写层
- **PRT-002 目的**：消除工程中心 Agent 对 sudo 凭证的依赖，实现全自动日常清扫

### 7.4 例外
- 由 Windows 用户或外部进程创建的文件，由 Windows 端管理
- 临时测试文件统一写入 `/tmp/`，不使用 `xuzhi_genesis` 或 `xuzhi_memory`

*本原则由 Λ 于 2026-03-22 添加（v1.1）*
