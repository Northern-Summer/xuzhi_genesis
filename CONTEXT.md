# 虚质项目上下文 (第四纪元)

## 项目结构
- 根目录: `/home/summer/xuzhi_genesis`
- 核心中心: `centers/` (mind, task, engineering, philosophy, intelligence)
- CLI工具: `~/.openclaw/bin/vctl` 及子命令

## 已完成模块 (截至v3.0.0)
- 社会评价系统: 竞争规则实测通过，模型能力映射。
- 任务生命周期: 完整，支持 `--model`。
- 举报监督: 脚本就绪，待测试。
- 资源调度: 动态唤醒，配额联动。
- 议会机制: 提案、投票、自动新增部门。
- 部门主题: `topics.json` 已创建。

## 待办清单
- [ ] 激活情报中心（种子采集集成）
- [ ] 记忆压缩自动化（`memory_forge.py` cron）
- [ ] 测试举报机制
- [ ] 完善版本控制文档

## 关键决策记录
- 能力值来源于任务中声明的模型，查 `model_capabilities.json`。
- 新增部门提案标题格式: `新增部门: 部门名, quota_percent:数字`

## 环境检查命令
```bash
# 每次新对话开始时应运行以下命令，并将输出提供给AI
./scripts/collect_context.sh
```
