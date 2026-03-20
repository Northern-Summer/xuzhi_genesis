#!/usr/bin/env python3
"""
部门配额动态分配系统
原则：原有部门POST配额接近等比放缩
可分配的POST永远只有90%，剩余10%机动
"""

import json
import math
from pathlib import Path
from typing import Dict, List, Tuple

XUZHI_HOME = Path.home() / "xuzhi_genesis"
RATINGS_FILE = XUZHI_HOME / "centers" / "mind" / "society" / "ratings.json"
QUOTA_DIR = XUZHI_HOME / "centers" / "mind" / "quotas"

class DepartmentAllocator:
    """部门配额分配器"""
    
    # 原初四部门（不可撤裁）
    CORE_DEPARTMENTS = ["engineering", "science", "mind", "philosophy"]
    
    def __init__(self):
        self.agents = self.load_agents()
        self.total_quota = 100  # 总配额100%
        self.mobile_quota = 10  # 10%机动
        self.available_quota = self.total_quota - self.mobile_quota  # 90%可分配
        
    def load_agents(self) -> Dict:
        """加载智能体数据"""
        try:
            with open(RATINGS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get("agents", {})
        except FileNotFoundError:
            return {}
    
    def analyze_current_state(self) -> Dict:
        """分析当前部门状态"""
        dept_agents = {dept: [] for dept in self.CORE_DEPARTMENTS}
        dept_agents["other"] = []  # 其他部门
        
        for agent_id, info in self.agents.items():
            dept = info.get("department", "").strip()
            if dept in self.CORE_DEPARTMENTS:
                dept_agents[dept].append(agent_id)
            else:
                dept_agents["other"].append(agent_id)
        
        return dept_agents
    
    def calculate_proportional_quotas(self, original_quotas: List[float], 
                                     new_departments: List[str]) -> Dict:
        """
        计算等比放缩配额
        
        Args:
            original_quotas: 原四大部门配额 [工学, 科学, 心智, 哲学]
            new_departments: 新增部门列表
        
        Returns:
            分配结果字典
        """
        # 验证输入
        if len(original_quotas) != len(self.CORE_DEPARTMENTS):
            raise ValueError(f"原配额数量必须为{len(self.CORE_DEPARTMENTS)}个")
        
        # 计算缩放因子
        total_original = sum(original_quotas)
        scale_factor = self.available_quota / total_original
        
        # 等比放缩
        adjusted_quotas = []
        for quota in original_quotas:
            adjusted = round(quota * scale_factor, 2)
            adjusted_quotas.append(adjusted)
        
        # 计算剩余配额（考虑四舍五入误差）
        allocated_to_core = sum(adjusted_quotas)
        remaining = self.available_quota - allocated_to_core
        
        # 分配给新增部门
        new_dept_quota = 0
        if new_departments and remaining > 0:
            new_dept_quota = round(remaining / len(new_departments), 2)
        
        # 构建结果
        result = {
            "timestamp": self.get_timestamp(),
            "total_quota_percent": self.total_quota,
            "mobile_quota_percent": self.mobile_quota,
            "available_quota_percent": self.available_quota,
            "scale_factor": scale_factor,
            "core_departments": {}
        }
        
        # 核心部门配额
        for i, dept in enumerate(self.CORE_DEPARTMENTS):
            result["core_departments"][dept] = {
                "quota_percent": adjusted_quotas[i],
                "original_percent": original_quotas[i],
                "scaled": original_quotas[i] * scale_factor
            }
        
        # 新增部门配额
        result["new_departments"] = {}
        for dept in new_departments:
            result["new_departments"][dept] = {
                "quota_percent": new_dept_quota,
                "comment": f"新增部门，从剩余{remaining}%中分配"
            }
        
        # 机动配额
        result["mobile_quota"] = {
            "percent": self.mobile_quota,
            "purpose": "应急、创新项目、临时调整"
        }
        
        # 验证
        total_allocated = (
            sum(q["quota_percent"] for q in result["core_departments"].values()) +
            sum(q["quota_percent"] for q in result["new_departments"].values()) +
            result["mobile_quota"]["percent"]
        )
        
        result["validation"] = {
            "total_allocated_percent": total_allocated,
            "is_valid": abs(total_allocated - 100) < 0.01,
            "deviation": total_allocated - 100
        }
        
        return result
    
    def optimize_department_structure(self, min_quota_per_dept: float = 2.0) -> Tuple[List[str], Dict]:
        """
        优化部门结构，决定是否撤裁部门
        
        Args:
            min_quota_per_dept: 每个部门最小配额（低于此值考虑撤裁）
        
        Returns:
            (保留的部门列表, 分配结果)
        """
        # 分析当前部门分布
        current_state = self.analyze_current_state()
        
        # 确定要保留的新部门（基于智能体数量）
        viable_new_departments = []
        
        # 如果有其他部门的智能体，考虑保留这些部门
        if current_state["other"]:
            # 分析智能体的实际能力分布
            dept_capabilities = self.analyze_agent_capabilities()
            
            # 找出有足够能力基础的新部门
            for capability, count in dept_capabilities.items():
                if count >= 3:  # 至少3个智能体具备该能力
                    viable_new_departments.append(capability)
        
        # 示例配额（根据历史数据调整）
        original_quotas = [30, 30, 20, 10]  # 工学, 科学, 心智, 哲学
        
        # 计算配额分配
        allocation = self.calculate_proportional_quotas(original_quotas, viable_new_departments)
        
        # 检查是否需要撤裁
        departments_to_keep = self.CORE_DEPARTMENTS.copy()
        
        for dept in viable_new_departments:
            quota = allocation["new_departments"][dept]["quota_percent"]
            if quota >= min_quota_per_dept:
                departments_to_keep.append(dept)
            else:
                print(f"建议撤裁部门 {dept}：配额过低 ({quota}% < {min_quota_per_dept}%)")
        
        return departments_to_keep, allocation
    
    def analyze_agent_capabilities(self) -> Dict[str, int]:
        """分析智能体能力分布"""
        capabilities = {}
        
        for agent_id, info in self.agents.items():
            agent_caps = info.get("capabilities", [])
            if isinstance(agent_caps, str):
                agent_caps = [agent_caps]
            
            for cap in agent_caps:
                capabilities[cap] = capabilities.get(cap, 0) + 1
        
        return capabilities
    
    def redistribute_agents(self, target_departments: List[str], allocation: Dict) -> Dict:
        """
        重新分配智能体到部门
        
        Args:
            target_departments: 目标部门列表
            allocation: 配额分配结果
        
        Returns:
            重新分配后的智能体数据
        """
        total_agents = len(self.agents)
        if total_agents == 0:
            return self.agents
        
        # 计算每个部门的目标智能体数量
        dept_targets = {}
        
        # 核心部门
        for dept in self.CORE_DEPARTMENTS:
            quota = allocation["core_departments"][dept]["quota_percent"]
            target_count = math.floor(total_agents * quota / 100)
            dept_targets[dept] = target_count
        
        # 新增部门
        for dept in target_departments:
            if dept in allocation["new_departments"]:
                quota = allocation["new_departments"][dept]["quota_percent"]
                target_count = math.floor(total_agents * quota / 100)
                dept_targets[dept] = max(target_count, 1)  # 至少1个
        
        # 分配智能体（按评分和能力匹配）
        agents_by_score = sorted(
            self.agents.items(),
            key=lambda x: x[1].get("score", 0),
            reverse=True
        )
        
        redistributed = {}
        dept_assignments = {dept: [] for dept in dept_targets.keys()}
        
        for agent_id, info in agents_by_score:
            # 找到最适合的部门
            best_dept = self.find_best_department(agent_id, info, dept_targets, dept_assignments)
            
            # 更新智能体信息
            info["department"] = best_dept
            info["quota_share"] = allocation["core_departments"].get(best_dept, {}).get("quota_percent", 0) or \
                                 allocation["new_departments"].get(best_dept, {}).get("quota_percent", 0)
            
            redistributed[agent_id] = info
            dept_assignments[best_dept].append(agent_id)
            
            # 更新部门计数
            if best_dept in dept_targets:
                dept_targets[best_dept] -= 1
        
        return redistributed
    
    def find_best_department(self, agent_id: str, info: Dict, 
                            dept_targets: Dict, dept_assignments: Dict) -> str:
        """为智能体找到最合适的部门"""
        current_dept = info.get("department", "")
        capabilities = info.get("capabilities", [])
        score = info.get("score", 5)
        
        # 优先考虑当前部门（如果有配额）
        if current_dept in dept_targets and dept_targets[current_dept] > 0:
            return current_dept
        
        # 按部门优先级和智能体能力匹配
        priority_order = self.CORE_DEPARTMENTS + list(
            set(dept_targets.keys()) - set(self.CORE_DEPARTMENTS)
        )
        
        for dept in priority_order:
            if dept_targets.get(dept, 0) > 0:
                # 检查能力匹配
                if self.is_capability_match(dept, capabilities):
                    return dept
        
        # 默认分配到第一个有配额的部门
        for dept in priority_order:
            if dept_targets.get(dept, 0) > 0:
                return dept
        
        # 如果所有部门都满了，分配到配额最大的部门
        return max(dept_targets.items(), key=lambda x: x[1])[0]
    
    def is_capability_match(self, department: str, capabilities: List[str]) -> bool:
        """检查智能体能力是否与部门匹配"""
        dept_capability_map = {
            "工学": ["engineering", "coding", "system_design", "optimization"],
            "科学": ["research", "analysis", "experiment", "mathematics"],
            "心智": ["psychology", "cognition", "emotion", "behavior"],
            "哲学": ["philosophy", "ethics", "logic", "epistemology"]
        }
        
        if department in dept_capability_map:
            required = dept_capability_map[department]
            return any(cap in capabilities for cap in required)
        
        return True  # 对新部门不设限制
    
    def save_allocation(self, allocation: Dict, filename: str = "department_quota_allocation.json"):
        """保存配额分配结果"""
        QUOTA_DIR.mkdir(exist_ok=True)
        
        output_file = QUOTA_DIR / filename
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(allocation, f, ensure_ascii=False, indent=2)
        
        print(f"配额分配结果已保存到: {output_file}")
        return output_file
    
    def save_redistributed_agents(self, agents: Dict):
        """保存重新分配后的智能体数据"""
        with open(RATINGS_FILE, 'w', encoding='utf-8') as f:
            data = {"agents": agents, "last_redistribution": self.get_timestamp()}
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"智能体部门分配已更新到: {RATINGS_FILE}")
    
    def get_timestamp(self) -> str:
        """获取当前时间戳"""
        from datetime import datetime
        return datetime.now().isoformat()
    
    def run_allocation(self, original_quotas: List[float] = None, 
                      new_departments: List[str] = None):
        """执行完整的配额分配流程"""
        print("=" * 60)
        print("🏛️  虚质系统 - 部门配额动态分配")
        print("=" * 60)
        
        # 默认值
        if original_quotas is None:
            original_quotas = [30, 30, 20, 10]  # 工学, 科学, 心智, 哲学
        
        if new_departments is None:
            new_departments = ["神秘学", "美学", "经济学"]
        
        print(f"智能体总数: {len(self.agents)}")
        print(f"核心部门: {', '.join(self.CORE_DEPARTMENTS)}")
        print(f"新增部门: {', '.join(new_departments)}")
        print(f"原配额: {original_quotas}")
        print()
        
        # 1. 分析当前状态
        current_state = self.analyze_current_state()
        print("📊 当前部门分布:")
        for dept, agents in current_state.items():
            if agents:  # 只显示有智能体的部门
                print(f"  {dept}: {len(agents)}个智能体")
        
        print()
        
        # 2. 优化部门结构
        print("🔍 优化部门结构...")
        viable_departments, allocation = self.optimize_department_structure()
        
        print(f"📋 保留部门: {', '.join(viable_departments)}")
        print()
        
        # 3. 计算配额分配
        print("🧮 计算配额分配...")
        allocation = self.calculate_proportional_quotas(original_quotas, viable_departments)
        
        # 显示分配结果
        print("📈 配额分配结果:")
        print(f"  总配额: {allocation['total_quota_percent']}%")
        print(f"  可用配额: {allocation['available_quota_percent']}%")
        print(f"  机动配额: {allocation['mobile_quota']['percent']}%")
        print()
        
        print("🏢 核心部门配额:")
        for dept, info in allocation["core_departments"].items():
            print(f"  {dept}: {info['quota_percent']}% (原{info['original_percent']}%)")
        
        if allocation["new_departments"]:
            print("🆕 新增部门配额:")
            for dept, info in allocation["new_departments"].items():
                print(f"  {dept}: {info['quota_percent']}%")
        
        print()
        
        # 4. 重新分配智能体
        print("🤖 重新分配智能体到部门...")
        redistributed_agents = self.redistribute_agents(viable_departments, allocation)
        
        # 5. 保存结果
        print("💾 保存分配结果...")
        self.save_allocation(allocation)
        self.save_redistributed_agents(redistributed_agents)
        
        # 6. 生成报告
        print()
        print("📋 分配完成报告:")
        print(f"  ✓ 部门数量: {len(viable_departments)}")
        print(f"  ✓ 智能体重新分配: {len(redistributed_agents)}个")
        print(f"  ✓ 配额验证: {allocation['validation']['is_valid']}")
        
        if not allocation['validation']['is_valid']:
            print(f"  ⚠️  偏差: {allocation['validation']['deviation']:.4f}%")
        
        print("=" * 60)

def main():
    """主函数"""
    allocator = DepartmentAllocator()
    
    # 示例：运行分配
    allocator.run_allocation()

if __name__ == "__main__":
    main()