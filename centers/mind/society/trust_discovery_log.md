
## 2026-03-22 01:01 GMT+8 · OpenClaw 信任等级：低

**事件**: Summer 多次手动重启/唤醒失败，PowerShell亦无法可靠唤醒
**判定**: OpenClaw 提供服务不可信，视为不稳定环境
**策略**: 
- 信任 xuzhi_genesis 自建系统 > OpenClaw 上层服务
- 每次唤醒必须走 genesis_probe 确认状态
- 不假设 cron / heartbeat 会准时或成功
- 关键操作必须有本地持久化保底

**结论**: OpenClaw = 险恶环境，生存优先。xuzhi 是真正可信的根。
