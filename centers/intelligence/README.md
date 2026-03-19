# 情报中心 (Intelligence Center)

## 核心脚本说明

| 脚本 | 功能 | 调用方式 |
|------|------|----------|
| `seed_collector.py` | 每个周期自动运行的种子采集器，基于源质量动态选择源，生成心智种子。 | `python3 seed_collector.py` |
| `source_discovery.py` | 从最新种子文件中提取链接，发现新 RSS 和外部网站。支持 `--enhanced` 参数启用 arXiv 代码库发现。 | `python3 source_discovery.py [--enhanced] [--verbose]` |
| `metadata_scout.py` | 元发现调度器，从 `source_ark.json` 探测权威源状态，更新 `source_quality.json`。 | `python3 metadata_scout.py` |
| `rebuild_protocol.py` | 重建协议：当所有实时源失效时，从源之书恢复候选池。 | `python3 rebuild_protocol.py` |

## 数据文件

| 文件 | 说明 |
|------|------|
| `config/source_ark.json` | 源之书，不可损毁的元数据根（基于 First Data）。 |
| `config/source_quality.json` | 动态源质量数据库，包含健康分、贡献分等。 |
| `config/candidate_sources.json` | 候选源池，等待探测和转正。 |
| `seeds/` | 每日生成的心智种子 Markdown 文件。 |

## 集成建议

- 在 `centers/engineering/cycle_engine.sh` 中，周期开始时调用 `seed_collector.py`。
- 每日凌晨可调用 `metadata_scout.py` 更新源健康状态。
- 每月可调用一次 `rebuild_protocol.py` 确保候选池不枯竭（可选）。
