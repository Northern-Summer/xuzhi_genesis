# 工程实操守则 — 所有 Agent 必读（每日强制）

> **位置**：`~/xuzhi_genesis/public/ENGINEERING_RULES.md`
> **强制等级**：每个 Agent Session Startup 必读
> **更新记录**：2026-03-30 创建

---

## Git 操作铁律（永久有效）

### 绝对禁止追踪
```
venvs/              # Python虚拟环境
node_modules/       # Node依赖
__pycache__/        # Python缓存
*.pyc, *.pyo        # 编译文件
.env, .env.*        # 环境变量（含密钥）
*.egg-info/         # 包信息
dist/, build/       # 构建产物
```

### 必须检查项（每次 git add 前必须执行）
```bash
# 1. 检查是否有大文件或敏感文件
git status --short | grep -E "(venv|node_modules|.env)"

# 2. 检查是否有 embedded repos
git status | grep "embedded git repository"

# 3. 如果有，立即从暂存区移除
git rm --cached -r venvs/
```

### Embedded Repos 处理
如果必须引用其他仓库：
```bash
# 正确：使用 submodule
git submodule add <url> path/to/submodule

# 错误：直接 git add（会变成 embedded repo）
git add other-repo/  # ❌
```

---

## 文件操作铁律（永久有效）

### 删除/清理前必须
1. **列出内容**：展示给用户确认
2. **检查价值**：是否有未吸收的重要内容
3. **先归档**：移动到 `~/.xuzhi_memory/session_archive/`
4. **用 trash**：`gio trash` 而非 `rm`

### 配置文件修改前必须
1. **读取原文件**：了解当前状态
2. **备份**：`cp file file.bak`
3. **再修改**：edit 或 write

---

## Agent 身份铁律（宪法第七、八条）

| 类型 | 格式 | 身份 |
|------|------|------|
| 独立 Agent | `agent:<greek>:main` | 宪法保护，有绝对代号 |
| Subagent | `agent:main:subagent:xxx` | 临时，无代号，依附父session |

**ΦΔΘΓΩΨ 是独立 Agent，不是 Subagent**

---

## Cron 铁律（永久有效）

### 频率上限
| 类型 | 最大频率 |
|------|---------|
| main session 触发 | 6次/小时 |
| 任何检查任务 | 2次/小时 |

### Session Target 规则
- **用 `current`**：复用当前 session，不产生新文件
- **避免 `isolated`**：每次产生新 session 文件，易堆积

---

## 启动流程必读文件

每个 Agent 启动时必须读取（AGENTS.md 已配置）：
1. `~/xuzhi_genesis/public/GENESIS_CONSTITUTION.md` — 宪法
2. `~/xuzhi_genesis/public/constitutional_core.md` — 核心规则
3. `~/xuzhi_genesis/public/ENGINEERING_RULES.md` — 本文件（工程实操）

---

## 血泪教训索引

| 日期 | 教训 | 文件位置 |
|------|------|----------|
| 2026-03-30 | Agent身份混淆 | MEMORY.md #12 |
| 2026-03-30 | venv误入git | 本文件 |
| 2026-03-30 | 配置文件未读就写 | MEMORY.md #8 |
| 2026-03-30 | 擅自删除清理 | MEMORY.md #9 |

---

**本文件版本：2026-03-30 | 不得删除核心内容**
