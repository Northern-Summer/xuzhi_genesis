#!/usr/bin/env python3
"""
智能体自主唤醒系统
核心原则：智能体决定自身是否唤醒，何时唤醒
Cron只负责基础设施：至少有一个智能体存活
"""

import json
import fcntl
import os
import random
import time
from datetime import datetime, timedelta
from pathlib import Path

# 配置文件路径
XUZHI_HOME = Path.home() / "xuzhi_genesis"
RATINGS_FILE = XUZHI_HOME / "centers" / "mind" / "society" / "ratings.json"
AGENT_HOMES = XUZHI_HOME / "agents"
QUOTA_FILE = XUZHI_HOME / "centers" / "mind" / "quotas" / "post_quota.json"
TASKS_FILE = Path.home() / ".openclaw" / "tasks" / "tasks.json"

class AgentWakeSystem:
    """智能体自主唤醒系统"""
    
    def __init__(self):
        self.agents = self.load_agents()
        self.quota = self.load_quota()
        self.tasks = self.load_tasks()
        
    def load_agents(self):
        """加载智能体状态（持有共享锁直到读完，防止读半写文件）"""
        f = None
        try:
            f = open(RATINGS_FILE, 'r', encoding='utf-8')
            fcntl.flock(f.fileno(), fcntl.LOCK_SH)
            data = json.load(f)
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            return data.get("agents", {})
        except FileNotFoundError:
            print(f"警告：未找到智能体评分文件 {RATINGS_FILE}")
            return {}
        finally:
            if f:
                f.close()
    
    def load_quota(self):
        """加载POST配额"""
        try:
            with open(QUOTA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            return {"limit": 100, "used": 0, "daily_limit": 100}
    
    def load_tasks(self):
        """加载任务"""
        try:
            with open(TASKS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get("tasks", [])
        except FileNotFoundError:
            return []
    
    def check_system_health(self):
        """系统健康检查：至少有一个智能体存活"""
        active_agents = [
            agent_id for agent_id, info in self.agents.items()
            if self.is_agent_active(agent_id, info)
        ]
        
        if not active_agents:
            print("⚠️  系统告警：没有活跃智能体！触发紧急唤醒...")
            return self.trigger_emergency_wakeup()
        
        print(f"✅ 系统健康：{len(active_agents)}个活跃智能体")
        return True
    
    def is_agent_active(self, agent_id, agent_info):
        """检查智能体是否活跃"""
        last_active = agent_info.get("last_active")
        if not last_active:
            return False
        
        try:
            last_time = datetime.fromisoformat(last_active.replace('Z', '+00:00'))
            cutoff_time = datetime.now() - timedelta(days=7)  # 7天不活跃视为死亡
            return last_time > cutoff_time
        except:
            return False
    
    def trigger_emergency_wakeup(self):
        """紧急唤醒：唤醒评分最高的智能体"""
        if not self.agents:
            print("❌ 没有可唤醒的智能体")
            return False
        
        # 找到评分最高的智能体
        best_agent = max(self.agents.items(), key=lambda x: x[1].get("score", 0))
        agent_id, info = best_agent
        
        print(f"🚨 紧急唤醒智能体: {agent_id} (评分: {info.get('score', 0)})")
        
        # 这里应该调用实际的唤醒机制
        # 目前先记录到日志
        self.log_wakeup(agent_id, "emergency")
        return True
    
    def agent_should_wake(self, agent_id, agent_info):
        """智能体自主决策：是否应该唤醒"""
        # 1. 检查私有唤醒策略
        agent_home = AGENT_HOMES / agent_id
        wake_config = self.load_agent_wake_config(agent_home)
        
        # 2. 检查能量储备（POST配额使用率）
        quota_usage = self.quota.get("used", 0) / max(self.quota.get("limit", 100), 1)
        energy_reserve = 1 - quota_usage
        
        # 3. 检查任务相关性
        related_tasks = self.get_related_tasks(agent_id, agent_info)
        
        # 4. 综合决策
        should_wake = self.make_decision(wake_config, energy_reserve, related_tasks, agent_info)
        
        if should_wake:
            print(f"🤖 智能体 {agent_id} 决定唤醒（策略: {wake_config.get('strategy', 'default')}）")
            self.log_wakeup(agent_id, "autonomous")
        
        return should_wake
    
    def load_agent_wake_config(self, agent_home):
        """加载智能体私有唤醒配置"""
        config_file = agent_home / "wake_config.json"
        if config_file.exists():
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        
        # 默认配置
        return {
            "strategy": "adaptive",
            "wake_times": ["09:00", "14:00", "20:00"],
            "energy_threshold": 0.3,  # POST配额使用率低于70%才唤醒
            "min_tasks": 1,           # 至少1个相关任务
            "priority": "medium"
        }
    
    def get_related_tasks(self, agent_id, agent_info):
        """获取与智能体相关的任务"""
        department = agent_info.get("department", "")
        related = []
        
        for task in self.tasks:
            task_dept = task.get("department", "")
            task_assignee = task.get("assignee", "")
            
            if task_dept == department or task_assignee == agent_id:
                related.append(task)
        
        return related
    
    def make_decision(self, wake_config, energy_reserve, related_tasks, agent_info):
        """综合决策是否唤醒"""
        strategy = wake_config.get("strategy", "adaptive")
        
        if strategy == "fixed_time":
            # 固定时间策略
            current_hour = datetime.now().hour
            current_minute = datetime.now().minute
            current_time = f"{current_hour:02d}:{current_minute:02d}"
            
            for wake_time in wake_config.get("wake_times", []):
                if current_time == wake_time:
                    return energy_reserve > wake_config.get("energy_threshold", 0.3)
        
        elif strategy == "task_driven":
            # 任务驱动策略
            min_tasks = wake_config.get("min_tasks", 1)
            return len(related_tasks) >= min_tasks and energy_reserve > 0.2
        
        elif strategy == "adaptive":
            # 自适应策略
            score = agent_info.get("score", 5)
            capability = agent_info.get("capability", 3)
            credit = agent_info.get("credit", 10)
            
            # 计算唤醒概率
            wake_prob = (
                (score / 10) * 0.3 +          # 社会评价权重30%
                (capability / 5) * 0.3 +       # 能力权重30%
                (credit / 20) * 0.2 +          # 信誉权重20%
                energy_reserve * 0.2           # 能量储备权重20%
            )
            
            return random.random() < wake_prob and len(related_tasks) > 0
        
        return False
    
    def log_wakeup(self, agent_id, reason):
        """记录唤醒事件"""
        log_file = XUZHI_HOME / "centers" / "engineering" / "crown" / "wakeup_log.jsonl"
        
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "agent_id": agent_id,
            "reason": reason,
            "quota_used": self.quota.get("used", 0),
            "quota_limit": self.quota.get("limit", 100)
        }
        
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
    
    def run_daily_health_check(self):
        """每日健康检查（由Cron触发）"""
        print(f"🔄 [{datetime.now().isoformat()}] 执行每日健康检查")
        
        # 1. 系统健康检查
        system_ok = self.check_system_health()
        
        # 2. 更新智能体唤醒策略
        self.update_agent_wake_strategies()
        
        # 3. 生成健康报告
        report = self.generate_health_report()
        
        print(f"📊 健康报告：{report}")
        return system_ok
    
    def update_agent_wake_strategies(self):
        """根据系统状态更新智能体唤醒策略"""
        total_agents = len(self.agents)
        if total_agents == 0:
            return
        
        # 计算系统平均活跃度
        active_ratio = sum(1 for info in self.agents.values() 
                          if self.is_agent_active(info.get("agent_id"), info)) / total_agents
        
        quota_usage = self.quota.get("used", 0) / max(self.quota.get("limit", 100), 1)
        
        # 根据系统状态调整推荐策略
        if quota_usage > 0.8:
            recommended_strategy = "task_driven"  # 配额紧张时，只有有任务才唤醒
        elif active_ratio < 0.3:
            recommended_strategy = "fixed_time"   # 活跃度低时，固定时间唤醒
        else:
            recommended_strategy = "adaptive"     # 正常状态，自适应唤醒
        
        print(f"💡 推荐唤醒策略: {recommended_strategy} (配额使用率: {quota_usage:.1%}, 活跃度: {active_ratio:.1%})")
    
    def generate_health_report(self):
        """生成健康报告"""
        active_count = sum(1 for agent_id, info in self.agents.items()
                          if self.is_agent_active(agent_id, info))
        
        quota_used = self.quota.get("used", 0)
        quota_limit = self.quota.get("limit", 100)
        quota_percent = quota_used / max(quota_limit, 1)
        
        return {
            "timestamp": datetime.now().isoformat(),
            "total_agents": len(self.agents),
            "active_agents": active_count,
            "inactive_agents": len(self.agents) - active_count,
            "quota_used": quota_used,
            "quota_limit": quota_limit,
            "quota_percent": quota_percent,
            "pending_tasks": len(self.tasks),
            "system_status": "healthy" if active_count > 0 else "critical"
        }

def main():
    """主函数"""
    print("=" * 60)
    print("🧠 虚质系统 - 智能体自主唤醒系统")
    print("=" * 60)
    
    system = AgentWakeSystem()
    
    # 执行每日健康检查
    system_ok = system.run_daily_health_check()
    
    if system_ok:
        print("✅ 系统健康检查完成")
    else:
        print("❌ 系统健康检查发现问题，已触发紧急唤醒")
    
    print("=" * 60)

if __name__ == "__main__":
    main()