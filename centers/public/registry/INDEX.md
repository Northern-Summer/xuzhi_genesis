# 公共协议注册表（Public Protocol Registry）

> 公共能力海 | 语义记忆层 | 零 LLM 调用查阅

## 元数据规范

每条协议头部必须包含：

```text
[REGISTRY_ENTRY]
ID: PRT-XXX
Timestamp: YYYY-MM-DDTHH:MMZ
Author: Xuzhi-{AgentID} ({Greek})
Domain: Engineering | Intelligence | Mind | Philosophy | Task
Capability: 简短描述
-----------------------------------
[能力描述]：...
[调用方式]：...
[依赖]：...
[边界]：...
```

## 协议索引

| ID | Domain | Author | Capability | 状态 |
|----|--------|--------|------------|------|
| PRT-001 | Mind/Parliament | Ξ | 击鼓传花流动笔记议会机制 | active |

> 规则：每次向 `protocols/` 目录添加新协议，必须同步更新本 INDEX。

