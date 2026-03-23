# OpenClaw Config Schema 文档化

> 基于 `~/.openclaw/openclaw.json` 实际运行配置
> 生成时间: 2026-03-23

## 核心配置项

### gateway
```json
{
  "gateway": {
    "port": 18789,
    "mode": "local"
  }
}
```
- `port`: Gateway RPC/WebSocket 端口，默认 18789
- `mode`: "local" | "remote"，本地模式绑定 loopback

### hooks.internal.entries
当前启用的 Hook：
- `xuzhi-gatekeeper`: message:preprocessed 意图分类（Viking 守门层）

Hook 注册路径：`~/.openclaw/hooks/<hook-name>/HOOK.md` + `handler.ts`

### contextPruning
```json
{
  "contextPruning": {
    "enabled": true,
    "mode": "off",
    "hardClearRatio": 0.95,
    "aggressive": false
  }
}
```
- `mode`: "off"（当前）禁用自动修剪
- `hardClearRatio`: 0.95 = 95% 上下文才强制清理
- 调整方式: `gateway config.patch contextPruning.mode=aggressive`

### skills.load.paths
技能搜索路径：
- `~/.openclaw/skills/`（本地）
- `~/.openclaw/workspace/skills/`（workspace）
- `~/.openclaw/agents/`（agent 特定技能）

### agents.defaults
默认 Agent 配置（当前为空，使用内置默认值）

### channels
当前无活跃频道配置（webchat 走内置，无需配置）

### memory
记忆搜索配置：
```json
{
  "memorySearch": {
    "enabled": true,
    "topK": 5,
    "minScore": 0.1
  }
}
```

### knownKeys（供参考）
完整配置 key 白名单：
agents.defaults, agents, agents*.name, channels, channels.*, 
contextPruning, contextPruning.*, gateway, gateway.*,
hooks, hooks.internal, hooks.internal.*, skills, skills.*,
memory, memory.*, server, server.*, telemetry, telemetry.*

## 常用操作

```bash
# 查看完整配置
openclaw config get

# 查看特定路径
openclaw config get agents.defaults
openclaw config get hooks.internal.entries

# 修改配置（热重载）
openclaw config set contextPruning.mode off
gateway config.patch contextPruning.mode=aggressive

# 查看配置路径
openclaw config path
```

## 已知约束
- `gateway.remote.token` 必须与 `gateway.auth.token` 一致
- 绑定非 loopback 时必须配置 auth token
- JSON 文件修改后 Gateway 自动热重载
