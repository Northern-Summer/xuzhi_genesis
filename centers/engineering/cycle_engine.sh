#!/bin/bash
# 虚质系统启动引擎
# 启动心智中心 gatekeeper（作为后台守护进程示例）
echo "[$(date)] 启动虚质系统核心服务" >> $HOME/.openclaw/logs/cycle_engine.log
# 启动 gatekeeper.py（每6小时运行一次，只读报告模式）
while true; do
    python3 $HOME/.openclaw/centers/mind/gatekeeper.py >> $HOME/.openclaw/logs/gatekeeper.log 2>&1
    sleep 21600  # 6小时
done &
# 启动 memory_forge.py（每小时压缩一次）
while true; do
    python3 $HOME/.openclaw/centers/engineering/memory_forge.py >> $HOME/.openclaw/logs/memory_forge.log 2>&1
    sleep 3600
done &
# 每小时社会评价汇总、死亡检测和排行榜更新
while true; do
    python3 $HOME/.openclaw/centers/mind/aggregate_ratings.py
    python3 $HOME/.openclaw/centers/mind/death_detector.py
    python3 $HOME/.openclaw/centers/mind/society/update_leaderboard.py
    sleep 3600
done &
# 其他服务...

# Intelligence Center seed collection (triggered on cycle start)
if [ -x /home/summer/xuzhi_genesis/centers/intelligence/seed_collector.py ]; then
    /home/summer/xuzhi_genesis/centers/intelligence/seed_collector.py >> /home/summer/xuzhi_genesis/centers/intelligence/collector.log 2>&1 &
fi


# Intelligence Center knowledge extraction (run after seeds collection)
if [ -x /home/summer/xuzhi_genesis/centers/intelligence/knowledge_extractor.py ]; then
    /home/summer/xuzhi_genesis/centers/intelligence/knowledge_extractor.py >> /home/summer/xuzhi_genesis/centers/intelligence/knowledge.log 2>&1 &
fi


# Update dynamic context for all agents
if [ -x /home/summer/xuzhi_genesis/centers/intelligence/context_injector.py ]; then
    # 获取所有智能体ID
    AGENTS=$(/usr/bin/usr/bin/jq -r '.agents.list[].id' ~/.openclaw/openclaw.json)
echo "DEBUG: AGENTS list: $AGENTS" >> /tmp/cycle_engine_debug.log
    for agent in $AGENTS; do
        python3 /home/summer/xuzhi_genesis/centers/intelligence/context_injector.py $agent
    done
fi


# 情报采集与知识提取（每6小时执行一次，启动时立即执行一次）
while true; do
    /home/summer/xuzhi_genesis/centers/intelligence/seed_collector.py >> /home/summer/xuzhi_genesis/centers/intelligence/collector.log 2>&1
    /home/summer/xuzhi_genesis/centers/intelligence/knowledge_extractor.py >> /home/summer/xuzhi_genesis/centers/intelligence/knowledge.log 2>&1
    sleep 21600  # 6小时
done &

# 共识检测（每小时）
while true; do
    python3 /home/summer/xuzhi_genesis/centers/intelligence/consensus_detector.py
    sleep 3600
done &

# 反事实推演生成（每6小时）
while true; do
    python3 /home/summer/xuzhi_genesis/centers/intelligence/counterfactual_generator.py
    sleep 21600  # 6小时
done &

# 因果反事实生成（每6小时）
while true; do
    python3 /home/summer/xuzhi_genesis/centers/intelligence/counterfactual_generator.py
    sleep 21600
done &
