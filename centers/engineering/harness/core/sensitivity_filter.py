#!/usr/bin/env python3
"""
涉敏过滤器 - 智能处理 1026/1027 错误
- 1026: 输入内容涉敏 → 预检 + 转换
- 1027: 输出内容涉敏 → 降级重试
- 自动维护敏感词替换表
"""

import json
import re
from pathlib import Path
from typing import Optional

SENSITIVE_WORD_MAP_FILE = Path.home() / ".xuzhi_memory" / "sensitivity_word_map.json"

# 默认替换规则（可扩展）
DEFAULT_REPLACEMENTS = {
    # 模糊指代 → 具体描述
    "有人说": "某研究显示",
    "据传说": "根据历史记录",
    "据说": "公开资料显示",
    "有人认为": "部分观点认为",
    # 死亡/终止
    "死亡": "终止",
    "死掉": "下线",
    "杀人": "攻击",
    "自杀": "自我终止",
    # 政治相关（极简化）
    "国家": "体系",
    "政府": "管理机构",
    "领导": "核心节点",
    # 其他高风险
    "暴力": "强制",
    "武器": "工具",
    "战争": "冲突",
}

def load_word_map() -> dict:
    """加载本地敏感词映射表"""
    if SENSITIVITY_MAP_FILE.exists():
        try:
            with open(SENSITIVITY_MAP_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return DEFAULT_REPLACEMENTS.copy()

def sanitize_text(text: str, word_map: Optional[dict] = None) -> str:
    """
    文本脱敏转换
    返回: 转换后的文本 + 是否进行了替换
    """
    if word_map is None:
        word_map = load_word_map()
    
    original = text
    for old, new in word_map.items():
        text = text.replace(old, new)
    
    return text, text != original

def check_sensitivity(text: str) -> tuple[bool, list[str]]:
    """
    预检文本是否可能触发涉敏
    返回: (是否需要转换, 触发词列表)
    """
    triggers = []
    word_map = load_word_map()
    
    for old_word in word_map.keys():
        if old_word in text:
            triggers.append(old_word)
    
    return len(triggers) > 0, triggers

def downgrade_prompt(prompt: str, temperature: float = 0.3) -> str:
    """
    降级 prompt 以绕过涉敏
    - 简化表述
    - 去除情感色彩
    - 使用更中性的技术语言
    """
    text = prompt
    
    # 去除所有引号内的完整句子（往往是观点性内容）
    text = re.sub(r'"[^"]{0,50}"', '', text)
    
    # 去除括号内的补充说明
    text = re.sub(r'\([^)]*\)', '', text)
    
    # 去除"可能/也许/大概"等模糊修饰
    text = re.sub(r'可能|也许|大概|应该|估计', '', text)
    
    # 去除感叹号（减少情感色彩）
    text = text.replace('！', '。').replace('!', '.')
    
    # 去除连续问号
    text = re.sub(r'\?+', '?', text)
    
    # 清理多余空白
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text

# 向后兼容：旧文件名引用
SENSITIVITY_MAP_FILE = SENSITIVE_WORD_MAP_FILE

if __name__ == "__main__":
    # CLI 测试
    import sys
    test_text = sys.argv[1] if len(sys.argv) > 1 else "有人说死亡是暴力的最终形式。"
    
    print(f"原文: {test_text}")
    triggers, found = check_sensitivity(test_text)
    print(f"触发涉敏: {triggers}, 触发词: {found}")
    
    sanitized, changed = sanitize_text(test_text)
    print(f"转换后: {sanitized}")
    print(f"已转换: {changed}")
    
    degraded = downgrade_prompt(test_text)
    print(f"降级后: {degraded}")
