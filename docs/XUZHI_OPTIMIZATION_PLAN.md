# Xuzhi 系统优雅化优化计划
## 基于 Claude Code 设计的精华提取与安全集成

> **版本**: 1.0  
> **日期**: 2026-04-01  
> **状态**: 规划中  
> **原则**: 绝对安全、可持续、不与 OpenClaw 官方更新冲突

---

## 一、安全集成原则

### 1.1 核心约束

| 约束 | 说明 |
|------|------|
| **不修改 OpenClaw 核心** | 所有改动在用户层（xuzhi_genesis、skills、hooks） |
| **利用扩展点** | 使用 OpenClaw 提供的 hooks、skills、agents、cron |
| **隔离层设计** | 通过适配层隔离，OpenClaw 更新不影响功能 |
| **向后兼容** | 新功能可独立禁用，不影响现有行为 |

### 1.2 扩展点映射

| Claude Code 特性 | OpenClaw 扩展点 | 实现位置 |
|------------------|-----------------|----------|
| 状态管理分层 | Hooks + Memory | `~/.openclaw/hooks/xuzhi-state/` |
| 任务后台化 | Cron isolated | 现有机制 + wrapper |
| 进度跟踪器 | Hooks (message:*) | `~/.openclaw/hooks/token-tracker/` |
| Vim 状态机 | Skills | `~/.openclaw/skills/vim-mode/` |
| 迁移系统 | Hooks (gateway:startup) | `~/.openclaw/hooks/xuzhi-migrate/` |

---

## 二、优先级矩阵

### 2.1 P0 - 立即实施

| 特性 | 价值 | 复杂度 | 风险 |
|------|------|--------|------|
| **Token 使用跟踪** | 高 | 低 | 低 |
| **状态管理优化** | 高 | 中 | 低 |

### 2.2 P1 - 短期实施

| 特性 | 价值 | 复杂度 | 风险 |
|------|------|--------|------|
| **迁移系统** | 中 | 低 | 低 |
| **Vim 模式技能** | 中 | 中 | 低 |

### 2.3 P2 - 长期规划

| 特性 | 价值 | 复杂度 | 风险 |
|------|------|--------|------|
| **远程会话桥接** | 高 | 高 | 中 |
| **任务后台化增强** | 中 | 中 | 低 |

---

## 三、详细设计

### 3.1 Token 使用跟踪器 (P0)

**目标**: 精确跟踪 Token 使用，支持预算管理和成本优化

**设计**:

```
消息流 → Hook (message:received, message:sent)
              ↓
         TokenTrackerStore
              ↓
         memory/usage/YYYY-MM.json
              ↓
         Cron 报告 (每日/每周)
```

**实现位置**: `~/.openclaw/hooks/token-tracker/`

**数据结构**:
```json
{
  "date": "2026-04-01",
  "sessions": {
    "agent:main:main": {
      "input_tokens": 15000,
      "output_tokens": 3500,
      "cache_tokens": 2000,
      "tool_calls": 12,
      "cost_usd": 0.45
    }
  },
  "total": {
    "input_tokens": 15000,
    "output_tokens": 3500,
    "cost_usd": 0.45
  }
}
```

**安全考虑**:
- 只读取消息，不修改
- 数据存储在用户目录
- 可独立禁用

---

### 3.2 状态管理优化 (P0)

**目标**: 解决 OpenClaw 状态散落问题，提供统一的状态视图

**设计**:

```
XuzhiStateProvider
├── SessionState (当前会话)
├── MemoryState (记忆系统)
├── AgentState (Agent 轮值)
├── TaskState (任务队列)
└── ConfigState (配置快照)
```

**实现位置**: `~/xuzhi_genesis/lib/state/`

**关键接口**:
```typescript
interface XuzhiState {
  session: {
    key: string;
    model: string;
    startTime: Date;
    messageCount: number;
  };
  memory: {
    todayFile: string;
    chunkCount: number;
    lastSync: Date;
  };
  epoch: {
    current: string;  // "Xi"
    startDate: Date;
    architect: string;
  };
  rotation: {
    today: AgentCode;
    tomorrow: AgentCode;
  };
}
```

**安全考虑**:
- 纯读取聚合，不修改 OpenClaw 状态
- 通过现有 API 获取数据
- 可独立禁用

---

### 3.3 迁移系统 (P1)

**目标**: 版本升级自动化，确保配置兼容性

**设计**:

```
gateway:startup → Hook
                      ↓
                 MigrationRunner
                      ↓
                 migrations/*.ts
                      ↓
                 记录到 migration_log.json
```

**实现位置**: `~/.openclaw/hooks/xuzhi-migrate/`

**迁移示例**:
```typescript
// migrations/001_fix_cron_channel.ts
export function migrate(): boolean {
  const jobs = readCronJobs();
  let changed = false;
  
  for (const job of jobs) {
    if (job.delivery?.channel === 'last' && !job.delivery.to) {
      job.delivery.to = 'openclaw-weixin';  // 默认 channel
      changed = true;
    }
  }
  
  if (changed) {
    writeCronJobs(jobs);
  }
  
  return changed;
}
```

**安全考虑**:
- 幂等操作，可安全多次运行
- 迁移前备份
- 记录迁移历史

---

### 3.4 Vim 模式技能 (P1)

**目标**: 为编辑任务提供 Vim 风格的高效操作

**设计**:

```
用户输入 → VimSkill
               ↓
          状态机解析
               ↓
          编辑操作
```

**实现位置**: `~/.openclaw/skills/vim-mode/`

**状态机**:
```typescript
type VimState = 
  | { mode: 'NORMAL'; pending: string }
  | { mode: 'INSERT'; text: string }
  | { mode: 'VISUAL'; selection: Range }
  | { mode: 'COMMAND'; buffer: string };

type VimAction =
  | { type: 'key'; key: string }
  | { type: 'motion'; motion: 'w' | 'b' | 'e' | '0' | '$' }
  | { type: 'operator'; op: 'd' | 'y' | 'c' };
```

**安全考虑**:
- 只影响明确启用的会话
- 不修改 OpenClaw 核心
- 可通过配置禁用

---

### 3.5 任务后台化增强 (P2)

**目标**: 支持 long-running 任务，会话可后台运行

**设计**:

```
当前会话 → Ctrl+B 两次
                  ↓
             后台化请求
                  ↓
        Cron isolated session
                  ↓
         输出到任务文件
                  ↓
         完成后通知
```

**实现位置**: `~/xuzhi_genesis/lib/tasks/`

**关键功能**:
- 会话状态保存
- 后台任务队列
- 进度通知机制
- 结果合并

**安全考虑**:
- 使用 OpenClaw 现有 isolated session 机制
- 不修改 OpenClaw 核心
- 任务文件存储在用户目录

---

## 四、实施路线图

### Phase 1: 基础设施 (本周)

1. **Token 跟踪器 Hook** (2h)
   - 创建 `~/.openclaw/hooks/token-tracker/`
   - 实现 message:* 事件处理
   - 测试与验证

2. **状态管理模块** (4h)
   - 创建 `~/xuzhi_genesis/lib/state/`
   - 实现状态聚合
   - Dashboard 集成

### Phase 2: 功能增强 (下周)

3. **迁移系统** (2h)
   - 创建 `~/.openclaw/hooks/xuzhi-migrate/`
   - 实现第一个迁移（cron channel 修复）
   - 测试与验证

4. **Vim 模式技能** (4h)
   - 创建 `~/.openclaw/skills/vim-mode/`
   - 实现基础状态机
   - 测试与验证

### Phase 3: 高级功能 (下月)

5. **任务后台化增强** (8h)
   - 设计后台任务协议
   - 实现任务管理器
   - 集成测试

---

## 五、风险与缓解

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| OpenClaw API 变更 | 低 | 中 | 隔离层 + 版本检测 |
| Hook 冲突 | 低 | 低 | 事件过滤 + 优先级 |
| 性能影响 | 中 | 低 | 异步处理 + 缓存 |
| 数据丢失 | 低 | 高 | 备份 + 原子写入 |

---

## 六、验收标准

### 6.1 Token 跟踪器

- [ ] message:received 事件正确捕获
- [ ] message:sent 事件正确捕获
- [ ] Token 统计准确（误差 < 5%）
- [ ] 数据持久化到 memory/usage/
- [ ] 可通过配置禁用

### 6.2 状态管理

- [ ] Dashboard 正确显示状态
- [ ] 状态更新延迟 < 100ms
- [ ] 支持状态快照导出
- [ ] 可通过配置禁用

### 6.3 迁移系统

- [ ] 启动时自动检测迁移
- [ ] 幂等运行（多次运行无副作用）
- [ ] 迁移历史可追溯
- [ ] 可通过配置禁用

---

## 七、维护指南

### 7.1 日常维护

```bash
# 检查 Hook 状态
openclaw hooks list

# 查看迁移日志
cat ~/.xuzhi_memory/logs/migration.json

# 查看使用统计
cat ~/.xuzhi_memory/usage/$(date +%Y-%m).json
```

### 7.2 故障排查

```bash
# 禁用所有自定义 Hook
openclaw hooks disable token-tracker
openclaw hooks disable xuzhi-migrate

# 检查日志
tail -f ~/.openclaw/gateway.log | grep -E "token-tracker|xuzhi"
```

---

*文档版本: 1.0 | 创建: 2026-04-01 | 作者: Ξ*
