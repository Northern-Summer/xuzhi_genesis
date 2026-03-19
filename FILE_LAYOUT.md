# 文件布局（截至 2026-03-18）
xuzhi_genesis/
├── backups/ # 所有备份和归档
├── centers/
│ ├── intelligence/ # 情报中心
│ │ ├── config/ # 源质量、源之书、候选源
│ │ ├── knowledge/ # 知识库 (knowledge.db, processed_seeds.txt)
│ │ ├── seeds/ # 心智种子文件
│ │ ├── *.py # 核心脚本
│ │ └── archive/ # (将创建) 存放旧脚本和临时文件
│ ├── mind/ # 心智中心
│ │ ├── parliament/ # 议会相关脚本
│ │ ├── society/ # 评分、排行榜
│ │ └── *.py # 其他脚本
│ ├── task/ # 任务中心
│ │ └── *.py
│ └── engineering/ # 工程中心
│ ├── crown/ # 配额监控
│ └── *.sh / *.py
├── logs/ # 统一日志目录
├── public/ # 静态资源（暂未使用）
└── scripts/ # 辅助脚本

