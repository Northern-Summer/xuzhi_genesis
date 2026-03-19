# 备份目录使用规则

- 所有备份为 `.tar.gz` 格式，命名 `YYYYMMDD_HHMMSS_描述.tar.gz`
- 禁止创建子目录
- 自动轮转：每日运行 `rotate_backups.sh`，保留最近10个备份
- 清理日志：`cleanup.log`
- 如需长期保留，请移出本目录或添加 `.keep` 后缀
