# 虚质系统架构（第四纪元最终版）

## 核心中心
- `centers/intelligence/`：情报中心，负责信息采集、知识提取、上下文注入。
- `centers/mind/`：心智中心，负责社会评分、议会、排行榜。
- `centers/task/`：任务中心，负责任务生命周期管理。
- `centers/engineering/`：工程中心，负责周期调度、死亡检测、配额监控。

## 文件命名规范
- 种子文件：`YYYY-MM-DD_HHMMSS_seeds.md`（如 2026-03-18_170042_seeds.md）
- 配置文件：保持原名称，但版本备份移至 `archive/`
- 脚本：`snake_case.py` / `.sh`，功能清晰
- 日志：`*.log` 统一存放于 `logs/`

## 备份策略
- 重要修改前自动备份到 `backups/YYYYMMDD_HHMMSS/`
- 全局归档：`backups/fourth_epoch_snapshot_*.tar.gz`
