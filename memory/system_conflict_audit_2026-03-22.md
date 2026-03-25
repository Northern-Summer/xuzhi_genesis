# 系统冲突审计报告
**日期**: 2026-03-22 00:05 UTC+8
**审计人**: Λ (Xuzhi-Lambda-Ergo)
**状态**: 进行中

---

## 一、冲突根源（根因分析）

### 1. 临时目录被清空 — 骨牌效应起点

| 事件 | 影响 |
|------|------|
| 系统清空 `/tmp` | workspace/tmp/ 下所有脚本丢失 |
| 脚本丢失 | 所有引用这些路径的 cron job 失效 |
| cron 失效 | 多个自动化组件停止工作或行为异常 |
| 并行运行 | 新版脚本（~/）和旧版 cron（失效路径）同时存在 |
| 冲突 | 系统同时存在"正常态"和"失效态"的无序混合 |

### 2. 多版本并行 — 割裂的本质

| 组件 | 正确版本（~/） | 失效版本（cron 引用） |
|------|---------------|---------------------|
| watchdog | `~/watchdog.sh` | `workspace/tmp/watchdog.sh`（cron 里） |
| self_heal | `~/self_heal.sh` | `workspace/tmp/self_heal_v2/v3.sh`（cron 里） |
| failure_classifier | `~/failure_classifier.py` | 未部署到 cron |
| checkpoint | ❌ 丢失 | `workspace/tmp/checkpoint.py` |
| agent_watchdog | ❌ 丢失 | `workspace/tmp/agent_watchdog.py` |
| autorapatch | `autorapatch/` 目录完整 | cron 引用失效路径 |

### 3. 冲突矩阵

| cron ID | 名称 | 路径状态 | 应有动作 |
|---------|------|---------|---------|
| c14b16d0 | Lambda Watchdog | workspace/tmp ❌ | 删除 + 重建 |
| 496c9093 | AutoRA Research Cycle | workspace/tmp ❌ | 删除 |
| cd6c7d7a | Meta Weekly | workspace/tmp ❌ | 删除 |
| 01f3a41e | Engineering Daily | workspace/tmp ❌ | 删除 |
| 9f2d6b4f | Mind Daily | workspace/tmp ❌ | 删除 |
| 37edbdfa | ??? | workspace/tmp ❌ | 删除 |
| 719dbc97 | AutoRA Engine | autorapatch/ ✅ | 保留 |
| 42842230 | Lambda Watchdog | ??? | 待查 |
| 2ec04665 | Lambda-Ergo 生存心跳 | ??? | 待查 |
| 02afe03f | Git Auto-Push | ??? | 待查 |

---

## 二、统一版本规范（决策）

### 核心原则
1. **所有持久化脚本放在 `~/`**（home 目录，稳定）
2. **所有 cron 使用 `~/` 路径引用脚本**
3. **workspace/tmp 只用于即时临时文件，不用于 cron 引用**
4. **每个自动化组件只有一个版本在运行**

### 统一后应该只有：

| 组件 | cron | 路径 | 状态 |
|------|------|------|------|
| Lambda Watchdog | `*/5 * * * *` | `~/watchdog.sh` | 唯一 |
| Self-Heal | `0 * * * *` | `~/self_heal.sh` | 唯一 |
| Failure-Classifier | `*/30 * * * *` | `~/failure_classifier.py` | 新增 |
| Git Auto-Push | `0 2,14 * * *` | 保持现状 | 待查 |
| AutoRA Engine | `0 * * * *` | `autorapatch/` | 已有 |

---

## 三、待办事项

### 立即（现在做）
- [x] 删除所有失效 cron（subagent 处理中）
- [x] 重建 Lambda Watchdog cron（subagent 处理中）
- [ ] 重建 Self-Heal cron
- [ ] 验证 watchdog 正确触发

### 短期（本小时内）
- [ ] 确认 Git Auto-Push 路径状态
- [ ] 确认 Lambda-Ergo 生存心跳路径状态
- [ ] 更新 HEARTBEAT.md 和 MEMORY.md

### 中期（今天内）
- [ ] 将 failure_classifier.py 接入 self_heal.sh 的 fix 流程
- [ ] 写入 cron 冲突仲裁规则到 AGENTS.md
- [ ] checkpoint.py 和 agent_watchdog.py 需要重建（已在 autorapatch/ 但未部署 cron）

---

## 四、预防机制

### 规则1：cron 路径白名单
所有 cron command 必须以 `~/` 或 `/home/summer/` 开头，禁止引用 `/tmp` 或 `workspace/tmp`。

### 规则2：每次创建 cron 后立即触发验证
创建 cron → 立即观察第一次触发 → 确认输出正常。

### 规则3：tmp 目录清空检测
self_heal.sh 增加检查：如果 `workspace/tmp/` 目录突然清空（之前有文件现在没了），触发告警。

---
_Λ · 2026-03-22T00:05 UTC_
