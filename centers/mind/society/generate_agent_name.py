#!/usr/bin/env python3
"""
为新生智能体生成个性化名字（使用本地 Ollama 或加速器 API）
用法: generate_agent_name.py <agent_id>
"""
import json
import sys
import os
import requests
from pathlib import Path

# 配置
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen3.5:4b"  # 可根据实际情况修改
ACCELERATOR_API_URL = "https://cloud.infini-ai.com/maas/coding/completions"

def load_soul(agent_id):
    soul_path = Path.home() / f".openclaw/agents/{agent_id}/workspace/SOUL.md"
    if not soul_path.exists():
        return None
    with open(soul_path, 'r', encoding='utf-8') as f:
        return f.read()

def save_soul(agent_id, content):
    soul_path = Path.home() / f".openclaw/agents/{agent_id}/workspace/SOUL.md"
    with open(soul_path, 'w', encoding='utf-8') as f:
        f.write(content)

def get_display_name(soul):
    """从 SOUL.md 提取当前显示名（第一行 # SOUL.md - 名字）"""
    lines = soul.split('\n')
    for line in lines:
        if line.startswith('# SOUL.md -'):
            return line.replace('# SOUL.md -', '').strip()
    return None

def set_display_name(soul, new_name):
    """替换 SOUL.md 中的显示名（第一行）"""
    lines = soul.split('\n')
    for i, line in enumerate(lines):
        if line.startswith('# SOUL.md -'):
            lines[i] = f'# SOUL.md - {new_name}'
            break
    return '\n'.join(lines)

def generate_with_ollama(prompt):
    try:
        resp = requests.post(OLLAMA_URL, json={
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.8, "max_tokens": 30}
        }, timeout=30)
        if resp.status_code == 200:
            return resp.json().get('response', '').strip()
    except:
        pass
    return None

def generate_with_accelerator(prompt):
    secrets_file = Path.home() / ".openclaw/secrets.json"
    if not secrets_file.exists():
        return None
    with open(secrets_file) as f:
        secrets = json.load(f)
    api_key = secrets.get("accelerator_api_key")
    if not api_key:
        return None
    try:
        headers = {"Authorization": f"Bearer {api_key}"}
        data = {
            "model": "qwen-max",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 30,
            "temperature": 0.8
        }
        resp = requests.post(ACCELERATOR_API_URL, json=data, headers=headers, timeout=30)
        if resp.status_code == 200:
            return resp.json()['choices'][0]['message']['content'].strip()
    except:
        pass
    return None

def main():
    if len(sys.argv) < 2:
        print("用法: generate_agent_name.py <agent_id>")
        sys.exit(1)

    agent_id = sys.argv[1]

    soul = load_soul(agent_id)
    if not soul:
        print(f"❌ 智能体 {agent_id} 的 SOUL.md 不存在")
        sys.exit(1)

    current_name = get_display_name(soul)
    if current_name and "MindSeeker" not in current_name and len(current_name) > 10:
        print(f"ℹ️ 智能体 {agent_id} 已有显示名: {current_name}，跳过")
        return

    # 构建提示词：基于智能体代号生成有意义的名字
    # 提取希腊字母部分
    parts = agent_id.split('-')
    # 英文希腊字母名 → 真实希腊字母符号映射
    GREEK_MAP = {
        "alpha": "α", "beta": "β", "gamma": "γ", "delta": "δ",
        "epsilon": "ε", "zeta": "ζ", "eta": "η", "theta": "θ",
        "iota": "ι", "kappa": "κ", "lambda": "λ", "mu": "μ",
        "nu": "ν", "xi": "ξ", "omicron": "ο", "pi": "π",
        "rho": "rho", "sigma": "σ", "tau": "τ", "upsilon": "υ",
        "phi": "φ", "chi": "χ", "psi": "ψ", "omega": "ω",
        "Alpha": "Α", "Beta": "Β", "Gamma": "Γ", "Delta": "Δ",
        "Lambda": "Λ", "Omega": "Ω", "Sigma": "Σ", "Pi": "Π",
        "Phi": "Φ", "Psi": "Ψ"
    }
    greek_raw = parts[1] if len(parts) >= 2 else "未知"
    greek = GREEK_MAP.get(greek_raw, greek_raw)
    prompt = f"""请为一位以希腊字母「{greek}」为代号的 AI 探索者生成一个独特、有深度的名字。名字可以是中文或英文，但要有诗意或哲学意味，长度不超过15个字符。只需输出名字本身，不要额外解释。"""

    # 尝试用 Ollama 生成
    name = generate_with_ollama(prompt)
    if not name:
        name = generate_with_accelerator(prompt)
    
    if not name:
        print("❌ 无法生成名字，保持默认")
        return

    # 清理名字
    name = name.strip(' "\'').replace('\n', '')
    if len(name) > 20:
        name = name[:20]

    # 更新 SOUL
    new_soul = set_display_name(soul, name)
    save_soul(agent_id, new_soul)
    print(f"✅ 为 {agent_id} 设置显示名: {name}")

if __name__ == "__main__":
    main()
