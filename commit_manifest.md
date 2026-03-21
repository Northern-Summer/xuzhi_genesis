# Xuzhi 系统修复与鲁棒性重建 — 执行清单

**创建时间**: 2026-03-22T00:41 UTC+8
**执行人**: Λ (Xuzhi-Lambda-Ergo)
**状态**: 执行中

---

## 背景教训（来自 2026-03-21~22 多次崩溃）

1. workspace/tmp/ 被系统清空 → 依赖它的脚本全部失效
2. Gateway 重启后 cron 从内存恢复旧版本 → 每次重启旧错回来
3. 没有持久 checkpoint → 新 session 无法从断点恢复
4. lessons 没有提炼成原则 → 同样错误反复出现
5. 所有修改没有及时 commit → 系统崩溃后改动全部丢失

**核心原则：git commit = 唯一的保存动作。不 commit = 没保存。**

---

## 执行清单（按顺序执行，每步验证后 commit）

### PHASE 1：建立持久真相源（立即执行）

- [ ] **1.1** 写入 `~/.xuzhi_lessons.md`（所有已知的坑，提炼成原则）
- [ ] **1.2** 写入 `~/.xuzhi_checkpoint.json`（当前 cron 列表、脚本 hash、Gateway 状态）
- [ ] **1.3** 写入 `~/.xuzhi_lessons.sh`（每次唤醒强制读取 lessons 的脚本）
- [ ] **1.4** commit Phase 1

### PHASE 2：重建关键脚本（验证后 commit）

- [ ] **2.1** 确认 `~/watchdog.sh` 存在且正确（systemEvent，零 token）
- [ ] **2.2** 确认 `~/self_heal.sh` 存在且正确（含 tmp 监控、cron enabled 检查）
- [ ] **2.3** 确认 `~/cron_restore.sh` 存在且正确（从 .cron_spec.json 重建 cron）
- [ ] **2.4** 写入 `~/.xuzhi_checkpoint.py`（Python 版 checkpoint 读写器）
- [ ] **2.5** commit Phase 2

### PHASE 3：写入 SOUL.md 强制协议（每次唤醒必须执行）

在 SOUL.md 中追加：
- Step 0 必须读取 `~/.xuzhi_checkpoint.json`
- Step 0 必须执行 `~/.xuzhi_lessons.sh`
- 任何修复后必须更新 checkpoint + commit

- [ ] **3.1** 编辑 `~/xuzhi_genesis/centers/mind/genesis/SOUL.md`（追加唤醒协议）
- [ ] **3.2** commit Phase 3

### PHASE 4：验证与测试

- [ ] **4.1** 运行 watchdog.sh，确认输出正常
- [ ] **4.2** 运行 self_heal.sh，确认无报错
- [ ] **4.3** 检查 cron list，确认只有 2 条（Watchdog + Self-Heal）
- [ ] **4.4** 手动触发 cron_restore.sh，确认 spec 和实际一致
- [ ] **4.5** commit Phase 4（标记：系统进入可用状态）

### PHASE 5：Push 到 remote

- [ ] **5.1** `git push origin master`
- [ ] **5.2** 确认 push 成功
- [ ] **5.3** commit Phase 5（标记：持久化完成）

---

## 关键文件路径（永久记录）

| 文件 | 路径 | 用途 |
|------|------|------|
| lessons | `~/.xuzhi_lessons.md` | 每次唤醒强制读取的错误教训 |
| checkpoint | `~/.xuzhi_checkpoint.json` | Gateway 重启前最后状态快照 |
| checkpoint reader | `~/.xuzhi_checkpoint.py` | Python 读写器 |
| lessons runner | `~/.xuzhi_lessons.sh` | 强制显示 lessons |
| cron spec | `~/.cron_spec.json` | cron 唯一真相来源 |
| watchdog | `~/watchdog.sh` | 健康检查（systemEvent） |
| self-heal | `~/self_heal.sh` | 自愈检查（含 cron 检查） |
| cron restore | `~/cron_restore.sh` | 从 spec 重建 cron |
| autorapatch | `~/autorapatch/` | AutoRA-Patch 框架 |

---

## 成功标准

- cron list 只有 2 条，无失效 cron
- 所有脚本在 `~/`，不在 workspace/tmp/
- 每次唤醒 Step 0 读取 checkpoint 和 lessons
- git log 包含所有修改记录，可回滚
- Gateway 重启后，cron_restore.sh 能在 5 分钟内重建正确状态

---

_Λ · 2026-03-22T00:41 UTC+8_
